from email_validator import validate_email, EmailNotValidError


class CSVValidator:
    def __init__(self, required_fields):
        self.required_fields = required_fields

    def validate_rows(self, rows):
        errors = []
        seen_projects = set()

        for i, row in enumerate(rows, start=2):
            for field in self.required_fields:
                if field not in row or not row[field].strip():
                    errors.append(f"Row {i}: Missing or empty value for '{field}'")

            project_name = row.get('project_name', '').strip()
            if project_name in seen_projects:
                errors.append(f"Row {i}: Duplicate project name '{project_name}'")
            else:
                seen_projects.add(project_name)

            email = row.get('email', '').strip()
            try:
                validate_email(email, check_deliverability=False)
            except EmailNotValidError as e:
                errors.append(f"Row {i}: Invalid email '{email}' - {str(e)}")

            password = row.get('password', '')
            if len(password) < 8:
                errors.append(f"Row {i}: Password must be at least 8 characters")

        return len(errors) == 0, errors
