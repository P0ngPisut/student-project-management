"""Offline policy tests; all addresses and passwords below are test fixtures."""

import unittest
from unittest.mock import patch

from backend.auth_validation import validate_email_format, validate_new_password


class EmailFormatTests(unittest.TestCase):
    def test_accepts_test_addresses_and_does_not_restrict_to_gmail(self):
        for address in (
            "student01@example.test",
            "advisor@example.org",
            "coordinator@example.com",
            "student+team@example.test",
        ):
            with self.subTest(address=address):
                self.assertEqual(validate_email_format(address), address)

    def test_rejects_malformed_addresses_not_just_missing_at(self):
        for address in (
            "",
            "student.example.test",
            "@example.test",
            "student@",
            "student@@example.test",
            "student@example",
            "student name@example.test",
            "student..name@example.test",
            "student@-example.test",
        ):
            with self.subTest(address=address):
                with self.assertRaisesRegex(ValueError, "^EMAIL_FORMAT_INVALID$"):
                    validate_email_format(address)

    def test_rejects_non_strings(self):
        for value in (None, 123, b"student@example.test"):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "^EMAIL_MUST_BE_STRING$"):
                    validate_email_format(value)

    def test_does_not_make_dns_or_network_calls(self):
        with (
            patch("dns.resolver.Resolver.resolve", side_effect=AssertionError("DNS used")),
            patch("dns.resolver.resolve", side_effect=AssertionError("DNS used")),
            patch("socket.getaddrinfo", side_effect=AssertionError("DNS used")),
            patch("socket.socket", side_effect=AssertionError("Network used")),
        ):
            self.assertEqual(
                validate_email_format("student@example.org"), "student@example.org"
            )
            self.assertEqual(
                validate_email_format("student@example.test"), "student@example.test"
            )

    def test_validation_preserves_input_for_later_v1_normalization(self):
        address = "Student01@EXAMPLE.TEST"
        self.assertEqual(validate_email_format(address), address)

    def test_error_message_does_not_echo_address(self):
        address = "test-personal-marker@@example.test"
        with self.assertRaises(ValueError) as caught:
            validate_email_format(address)
        self.assertNotIn(address, str(caught.exception))


class NewPasswordTests(unittest.TestCase):
    def test_accepts_exactly_eight_characters(self):
        self.assertEqual(validate_new_password("Demo1234"), "Demo1234")

    def test_rejects_seven_characters_even_with_uppercase_and_digit(self):
        with self.assertRaisesRegex(ValueError, "^PASSWORD_TOO_SHORT$"):
            validate_new_password("Demo123")

    def test_rejects_missing_uppercase(self):
        with self.assertRaisesRegex(ValueError, "^PASSWORD_UPPERCASE_REQUIRED$"):
            validate_new_password("demo1234")

    def test_rejects_missing_digit(self):
        with self.assertRaisesRegex(ValueError, "^PASSWORD_DIGIT_REQUIRED$"):
            validate_new_password("DemoTest")

    def test_does_not_require_lowercase(self):
        self.assertEqual(validate_new_password("ABCDEFG1"), "ABCDEFG1")

    def test_does_not_require_special_characters(self):
        self.assertEqual(validate_new_password("Demo12345"), "Demo12345")

    def test_preserves_spaces_and_case(self):
        password = " Demo1234 "
        self.assertEqual(validate_new_password(password), password)

    def test_accepts_special_characters(self):
        self.assertEqual(validate_new_password("Demo123!"), "Demo123!")

    def test_rejects_empty_password(self):
        with self.assertRaisesRegex(ValueError, "^PASSWORD_TOO_SHORT$"):
            validate_new_password("")

    def test_rejects_non_strings(self):
        for value in (None, 12345678, b"Demo1234"):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "^PASSWORD_MUST_BE_STRING$"):
                    validate_new_password(value)

    def test_error_message_does_not_echo_password(self):
        password = "demo1234-fixture"
        with self.assertRaises(ValueError) as caught:
            validate_new_password(password)
        self.assertNotIn(password, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
