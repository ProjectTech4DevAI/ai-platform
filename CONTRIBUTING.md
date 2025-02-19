# Contributing to Tech4Dev AI Platform

Thank you for considering contributing to **Tech4Dev AI Platform**! We welcome contributions of all kinds, including bug reports, feature requests, documentation improvements, and code contributions.

Before you begin, **please refer to the repository's [README](https://github.com/ProjectTech4DevAI/ai-platform/blob/main/README.md) and [Wiki](https://github.com/ProjectTech4DevAI/ai-platform/wiki)** for an overview of the project and setup instructions.

---

## 📌 Getting Started
To contribute effectively, you need to set up the project on your local machine. Follow the steps below to get started.

---

## 📌 How to Contribute

###  Fork the Repository
1. Click the **Fork** button on the top right of this repository.
2. Clone your forked repository:
   ```
   git clone https://github.com/ProjectTech4DevAI/ai-platform.git
   cd ai-platform
   ```

###  Create a Branch
Always work in a new branch based on main (or develop). Use a descriptive branch name:
   ```
   git checkout -b feature/new-feature-name
   ```

###  Make and Test Changes
1. Adhere to the project's established coding style for consistency.
2. Ensure the code is well-documented.
3. If you've resolved a bug or implemented a new feature, make sure to include appropriate test cases and confirm they pass successfully. Execute tests before committing your changes:
   ```
   pytest
   ```

###  Run Pre-Commit Hooks
Before pushing your changes, ensure they follow project conventions by running:
   ```
   poetry run pre-commit run --all-files
   ```
This ensures that your code is properly formatted and meets style guidelines.

###  Verify Application Functionality
Before submitting a pull request, please ensure that you ran the application using:
   ```
   poetry run uvicorn src.app.main:app --reload
   ```
and verify that everything functions as expected.

###  Commit Changes
Use descriptive commit messages:
   ```
   git commit -m "one liner for the commit"
   ```

###  Push and Open a Pull Request (PR)
Don't forget to link the PR to the issue if you are solving one. Push your changes to GitHub:
   ```
   git push origin feature/your-feature-name
   ```
Open a Pull Request (PR) in the main repository.

###  Code Style and Best Practices

