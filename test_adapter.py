import unittest

from adapter import prefix_for_input_type, prefix_input


class PrefixTests(unittest.TestCase):
    def test_query(self):
        self.assertEqual(prefix_input("hello", prefix_for_input_type("search_query")), "search_query: hello")

    def test_document_batch(self):
        self.assertEqual(
            prefix_input(["one", "two"], prefix_for_input_type("search_document")),
            ["search_document: one", "search_document: two"],
        )

    def test_existing_prefix_is_not_duplicated(self):
        self.assertEqual(prefix_input("search_query: hello", "search_query: "), "search_query: hello")

    def test_untyped_input_is_rejected(self):
        with self.assertRaises(ValueError):
            prefix_input("hello", None)


if __name__ == "__main__":
    unittest.main()
