import warnings

warnings.filterwarnings("ignore")

from langfuse import Langfuse

from sentence_transformers import SentenceTransformer

embedding_model = SentenceTransformer("all-mpnet-base-v2")


import os

os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-xx"
os.environ["LANGFUSE_SECRET_KEY"] = "sk-xx"
os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"
os.environ["OPENAI_API_KEY"] = "sk-proj-Yxxx"
os.environ["TOKENIZERS_PARALLELISM"] = "true"

langfuse = Langfuse()


PAGES_TO_FETCH = 2

traces = []
for i in range(PAGES_TO_FETCH):
    traces_page = langfuse.fetch_traces(page=i + 1)
    traces.extend(traces_page.data)

traces_list = []
for trace in traces:
    trace_info = [trace.id, trace.input]
    traces_list.append(trace_info)

import pandas as pd

cluster_traces_df = pd.DataFrame(traces_list, columns=["trace_id", "message"])
cluster_traces_df.dropna(inplace=True)  # drop traces with message = None

# keep only rows whose message is NOT in bad
cluster_traces_df = cluster_traces_df[
    ~cluster_traces_df["message"].isin(["setup_thread", "validate_thread", "RunID"])
]

# (optional) reset the index if you don’t care about preserving the old one
cluster_traces_df = cluster_traces_df.reset_index(drop=True)

# naive implementation (batch=1)
cluster_traces_df["embeddings"] = cluster_traces_df["message"].map(
    embedding_model.encode
)

# use batches to speed up embedding
from tqdm import tqdm

batch_size = 512  # Choose an appropriate batch size based on your model and hardware capabilities
messages = cluster_traces_df["message"].tolist()
embeddings = []

# Use tqdm to wrap your range function for the progress bar
for i in tqdm(range(0, len(messages), batch_size), desc="Encoding batches"):
    batch = messages[i : i + batch_size]
    batch_embeddings = embedding_model.encode(batch)
    embeddings.extend(batch_embeddings)

cluster_traces_df["embeddings"] = embeddings


import hdbscan

clusterer = hdbscan.HDBSCAN(min_cluster_size=4)
cluster_traces_df["cluster"] = clusterer.fit_predict(
    cluster_traces_df["embeddings"].to_list()
)

cluster_traces_df["cluster"].value_counts().head(2).to_dict()


import openai

# Note: Depending on the volume of data you are running,
# you may want to limit the number of utterances representing each group (ex. utterances_group[:5])


def generate_label(message_group):
    prompt = f"""
        # Task
        Your goal is to assign an intent label that most accurately fits the given group of utterances.
        You will only provide a single label, no explanation.  The label should be snake cased.

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
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
    )
    return response.choices[0].message.content.strip()


print(cluster_traces_df)
for cluster in cluster_traces_df["cluster"].unique():
    if cluster == -1:
        continue
    messages_in_cluster = cluster_traces_df[cluster_traces_df["cluster"] == cluster][
        "message"
    ]

    # sample if too many messages
    if len(messages_in_cluster) > 50:
        messages_in_cluster = messages_in_cluster.sample(50)

    label = generate_label(messages_in_cluster)
    cluster_traces_df.loc[
        cluster_traces_df["cluster"] == cluster, "cluster_label"
    ] = label


cluster_traces_df["cluster_label"].value_counts().head(20).to_dict()

# explore the messages sent within a specific cluster
cluster_traces_df[
    cluster_traces_df["cluster_label"] == "trace_in_langfuse"
].message.head(20).to_dict()

# add as labels back to langfuse
for index, row in cluster_traces_df.iterrows():
    if row["cluster"] != -1:
        trace_id = row["trace_id"]
        label = row["cluster_label"]
        langfuse.trace(id=trace_id, tags=[label])
