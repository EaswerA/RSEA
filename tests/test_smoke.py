import unittest


class SmokeTests(unittest.TestCase):
    def test_backend_app_imports_from_workspace_root(self):
        # Guard against module import regressions in package mode.
        import backend.app  # noqa: F401

    def test_normalize_data_accepts_list_input(self):
        from backend.normalizer import normalize_data

        source = [
            {
                "component": "RAM",
                "type": "hardware",
                "value": "1024",
                "unit": "mb",
            }
        ]

        result = normalize_data(source)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["component"], "ram")
        self.assertEqual(result[0]["type"], "Hardware")
        self.assertEqual(result[0]["unit"], "GB")
        self.assertEqual(result[0]["value"], 1.0)


if __name__ == "__main__":
    unittest.main()