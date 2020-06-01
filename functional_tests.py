import unittest
import subprocess


class UserCanPassCommandLineArgumentsTest(unittest.TestCase):

    def setUp(self):
        self.LOCATION = 'vancouver'
        self.CLOUD_FN_ENDPOINT = 'https://cloud-function-location-project-name.cloudfunctions.net/function-name'
        self.WINDOW_DATETIME_START = '2020-01-01 00:00'
        self.WINDOW_LENGTH_HOURS = 1

    def test_user_can_execute_script_with_required_command_line_arguments(self):
        """
        Simulate executing the script with required command line arguments. A return code of zero indicates the
        script executed successfully with no errors.

            python main.py \
            --location=vancouver \
            --window_datetime_start='2020-01-01 00:00' \
            --window_length_hours=1 \
            --cloud_function_endpoint=https://cloud-function-location-project-name.cloudfunctions.net/function-name

        """

        process = subprocess.run(['python',
                                  'main.py',
                                  f'--location={self.LOCATION}',
                                  f'--window_datetime_start={self.WINDOW_DATETIME_START}',
                                  f'--window_length_hours={self.WINDOW_LENGTH_HOURS}',
                                  f'--cloud_function_endpoint={self.CLOUD_FN_ENDPOINT}'])

        self.assertEqual(0, process.returncode)

    def test_script_returns_non_zero_return_code_with_missing_command_line_arguments(self):
        """
         Simulate executing the script with missing required command line arguments. A return non-zero code indicates
         the script encountered errors.

            python main_v1.py \
            --location=vancouver \
            --cloud_function_endpoint=https://cloud-function-location-project-name.cloudfunctions.net/function-name

        """
        process = subprocess.run(['python', 'main.py'])
        self.assertNotEqual(0, process.returncode)


if __name__ == '__main__':
    unittest.main()
