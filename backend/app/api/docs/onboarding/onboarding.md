# Onboarding API Behavior

## 🏢 Organization Handling
- If `organization_name` does **not exist**, a new organization will be created.
- If `organization_name` already exists, the request will proceed to create the project under that organization.

---

## 📂 Project Handling
- If `project_name` does **not exist** in the organization, it will be created.
- If the project already exists in the same organization, the API will return **409 Conflict**.

---

## 👤 User Handling
- If `email` does **not exist**, a new user is created and linked to the project.
- If the user already exists, they are simply attached to the project.

---

## 🔑 OpenAI API Key (Optional)
- If provided, the API key will be **encrypted** and stored as project credentials.
- If omitted, the project will be created **without OpenAI credentials**.
- The return response includes a masked openai_key if provided.

---

## 🔄 Transactional Guarantee
The onboarding process is **all-or-nothing**:
- If any step fails (e.g., invalid password), **no organization, project, or user will be persisted**.
