"""Input validation for the classroom project's proposed authentication flow.

These helpers do not authenticate, create accounts, or access the database.
They return the original input; account storage/identity normalization belongs
to the eventual provisioning flow and must follow Schema V1.
"""

from email_validator import EmailNotValidError, validate_email


def validate_email_format(value: str) -> str:
    """Validate syntax without DNS/mailbox checks, including .test addresses."""
    if not isinstance(value, str):
        raise ValueError("EMAIL_MUST_BE_STRING")

    try:
        validate_email(value, check_deliverability=False, test_environment=True)
    except EmailNotValidError:
        # Do not expose the supplied address through library error messages.
        raise ValueError("EMAIL_FORMAT_INVALID") from None

    return value


def validate_new_password(value: str) -> str:
    """Require at least 8 characters, one A-Z character, and one 0-9 digit.

    No lowercase or special character is required. Do not trim or change case.
    This checks a new password's policy, not whether a login password matches.
    """
    if not isinstance(value, str):
        raise ValueError("PASSWORD_MUST_BE_STRING")
    if len(value) < 8:
        raise ValueError("PASSWORD_TOO_SHORT")
    if not any("A" <= character <= "Z" for character in value):
        raise ValueError("PASSWORD_UPPERCASE_REQUIRED")
    if not any("0" <= character <= "9" for character in value):
        raise ValueError("PASSWORD_DIGIT_REQUIRED")

    return value
