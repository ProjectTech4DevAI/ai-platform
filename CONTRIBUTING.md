# Contributing to Tech4Dev AI Platform

Thank you for considering contributing to **Tech4Dev AI Platform**! We welcome contributions of all kinds, including bug reports, feature requests, documentation improvements, and code contributions.

---

## 📌 Getting Started
To contribute successfully, you must first set up the project on your local machine. Please follow the instructions outlined in the project's README to configure the repository and begin your contributions.

Before you proceed, **make sure to check the repository's [README](https://github.com/ProjectTech4DevAI/ai-platform/blob/main/backend/README.md) for a comprehensive overview of the project's backend and detailed setup guidelines.**

---

## 📌 How to Contribute

### Fork the Repository
1. Click the **Fork** button on the top right of this repository.
2. Clone your forked repository:
```
git clone https://github.com/{username}/ai-platform.git
cd ai-platform
```

### Create a Branch
• Always work in a new branch based on main.
• For branch name, follow this convention: ``type/one-line-description``
   e.g. ``enhancement/support-openai-citation-new-format``

**Type** can be:
   - enhancement
   - bugfix
   - feature


 ```
 git checkout -b type/one-line-description
 ```

### Make and Test Changes
1. Adhere to the project's established coding style for consistency.
2. Make sure the code adheres to best practices.
3. If you've resolved a bug or implemented a new feature, make sure to include appropriate test cases and confirm they pass successfully. Execute tests before committing your changes.
```
bash ./scripts/test.sh
```
### Verify Application Functionality
Before submitting a pull request, please ensure that you ran the application using:
```
fastapi run --reload app/main.py
```
and verify that everything functions as expected.

### Commit Changes
Use descriptive commit messages:
```
git commit -m "one liner for the commit"
```

### Push and Open a Pull Request (PR)
• For PR name, follow this convention:
   ``Module Name: One liner of changes``

• Don't forget to link the PR to the issue if you are solving one.

• Push your changes to GitHub:
```
git push origin Module Name: One liner of changes
```
We will be looking forward to your contributions!
