import warnings
from typing import List, Dict, Any
import pandas as pd
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from langfuse import Langfuse
from sqlmodel import Session
from app.crud.credentials import get_provider_credential
from app.core import settings

warnings.filterwarnings("ignore")


class LangfuseExperiment:
    def __init__(self, db: Session, org_id: str, project_id: str = None):
        self.db = db
        self.org_id = org_id
        self.project_id = project_id
        self.embedding_model = SentenceTransformer("all-mpnet-base-v2")
        self.langfuse = self._initialize_langfuse()

    def _initialize_langfuse(self) -> Langfuse:
        """Initialize Langfuse client with credentials from database."""
        credentials = get_provider_credential(
            session=self.db,
            org_id=self.org_id,
            provider="langfuse",
            project_id=self.project_id,
        )

        if not credentials:
            raise ValueError("Langfuse credentials not found in database")

        return Langfuse(
            public_key=credentials["public_key"],
            secret_key=credentials["secret_key"],
            host=credentials["host"],
        )

    def fetch_traces(self, pages_to_fetch: int = 2) -> List[Dict[str, Any]]:
        """Fetch traces from Langfuse."""
        traces = []
        for i in range(pages_to_fetch):
            traces_page = self.langfuse.fetch_traces(page=i + 1)
            traces.extend(traces_page.data)
        return traces

    def prepare_traces_dataframe(self, traces: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert traces to DataFrame and clean data."""
        traces_list = [[trace.id, trace.input] for trace in traces]
        df = pd.DataFrame(traces_list, columns=["trace_id", "message"])
        df.dropna(inplace=True)

        # Filter out system messages
        df = df[~df["message"].isin(["setup_thread", "validate_thread", "RunID"])]
        df = df.reset_index(drop=True)
        return df

    def generate_embeddings(
        self, df: pd.DataFrame, batch_size: int = 512
    ) -> pd.DataFrame:
        """Generate embeddings for messages in batches."""
        messages = df["message"].tolist()
        embeddings = []

        for i in tqdm(range(0, len(messages), batch_size), desc="Encoding batches"):
            batch = messages[i : i + batch_size]
            batch_embeddings = self.embedding_model.encode(batch)
            embeddings.extend(batch_embeddings)

        df["embeddings"] = embeddings
        return df

    def cluster_traces(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cluster traces using HDBSCAN."""
        import hdbscan

        clusterer = hdbscan.HDBSCAN(min_cluster_size=4)
        df["cluster"] = clusterer.fit_predict(df["embeddings"].to_list())
        return df

    def generate_cluster_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate labels for clusters using OpenAI."""
        import openai

        for cluster in df["cluster"].unique():
            if cluster == -1:
                continue

            messages_in_cluster = df[df["cluster"] == cluster]["message"]

            # Sample if too many messages
            if len(messages_in_cluster) > 50:
                messages_in_cluster = messages_in_cluster.sample(50)

            label = self._generate_label(messages_in_cluster)
            df.loc[df["cluster"] == cluster, "cluster_label"] = label

        return df

    def _generate_label(self, message_group: pd.Series) -> str:
        """Generate a label for a group of messages using OpenAI."""
        import openai

        prompt = f"""
            # Task
            Your goal is to assign an intent label that most accurately fits the given group of utterances.
            You will only provide a single label, no explanation. The label should be snake cased.

            ## Example utterances
            so long
            bye

            ## Example labels
            goodbye
            end_conversation

            Utterances: {message_group}
            Label:
        """

        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
        )
        return response.choices[0].message.content.strip()

    def update_langfuse_traces(self, df: pd.DataFrame) -> None:
        """Update traces in Langfuse with cluster labels."""
        for _, row in df.iterrows():
            if row["cluster"] != -1:
                self.langfuse.trace(id=row["trace_id"], tags=[row["cluster_label"]])

    def run_experiment(self, pages_to_fetch: int = 2) -> pd.DataFrame:
        """Run the complete experiment pipeline."""
        # Fetch traces
        traces = self.fetch_traces(pages_to_fetch)

        # Prepare DataFrame
        df = self.prepare_traces_dataframe(traces)

        # Generate embeddings
        df = self.generate_embeddings(df)

        # Cluster traces
        df = self.cluster_traces(df)

        # Generate labels
        df = self.generate_cluster_labels(df)

        # Update Langfuse
        self.update_langfuse_traces(df)

        return df


# Example usage:
# experiment = LangfuseExperiment(db=session, org_id="org_123", project_id="proj_456")
# results_df = experiment.run_experiment()
