from fake_useragent import FakeUserAgentError
from unittest import mock, TestCase
from bs4 import BeautifulSoup
import argparse
import datetime
import templates
import requests
import responses
import main
import json
import sys


class TestMain(TestCase):

    def setUp(self):
        self.TEST_CLOUD_FN_ENDPOINT = 'https://cloud-function-location-project-name.cloudfunctions.net/function-name'
        self.TEST_LOCATION = 'vancouver'
        self.TEST_POST_URL = 'https://vancouver.craigslist.org/van/apa/d/nice-place-to-live/7129935096.html'
        self.TEST_WINDOW_DATETIME_START = '2020-01-01 00:00'
        self.TEST_WINDOW_LENGTH_HOURS = 1
        self.TEST_COMMAND_LINE_ARGS = [f'--location={self.TEST_LOCATION}',
                                       f'--window_datetime_start={self.TEST_WINDOW_DATETIME_START}',
                                       f'--window_length_hours={self.TEST_WINDOW_LENGTH_HOURS}',
                                       f'--cloud_function_endpoint={self.TEST_CLOUD_FN_ENDPOINT}']
        self.TEST_ARGS_NAMESPACE = argparse.Namespace(location=self.TEST_LOCATION,
                                                      window_datetime_start=self.TEST_WINDOW_DATETIME_START,
                                                      window_length_hours=self.TEST_WINDOW_LENGTH_HOURS,
                                                      cloud_function_endpoint=self.TEST_CLOUD_FN_ENDPOINT)
        with open('sample_html_response.txt', 'r') as fin:
            self.TEST_HTML = fin.read()

        self.TEST_SOUP = BeautifulSoup(self.TEST_HTML, 'html.parser')

    def test_parse_args(self):
        """
        Test command line arguments are parsed
        """
        self.assertEqual(main.parse_args(self.TEST_COMMAND_LINE_ARGS), self.TEST_ARGS_NAMESPACE)

    def test_validate_url_with_valid_url(self):
        """
        Test valid URL is accepted with no exceptions raised
        """
        valid_url_to_check = 'https://vancouver.craigslist.org/search/apa'
        self.assertIsNone(main.validate_url(valid_url_to_check))

    def test_validate_url_with_invalid_url_raises_value_error(self):
        """
        Test invalid URL raises ValueError
        """
        invalid_url_to_check = 'https://comox.valley.craigslist.org/search/apa'
        with self.assertRaises(ValueError):
            main.validate_url(invalid_url_to_check)

    @responses.activate
    def test_get_html_with_params_headers_args(self):
        """
        Test the function performs the GET request and returns html text
        """
        url_to_get = 'https://vancouver.craigslist.org/search/apa'
        headers = templates.HEADERS.copy()
        headers.update({
            'Host': f'{self.TEST_LOCATION}.craigslist.org',
            'Referer': f'https://{self.TEST_LOCATION}.craigslist.org/d/apts-housing-for-rent/search/apa',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'
        })
        responses.add(method=responses.GET, url=url_to_get, status=200, body=self.TEST_HTML)
        self.assertEqual(main.get_html(url_to_get=url_to_get,
                                       headers=headers,
                                       params=templates.CL_PARAMS,
                                       args=self.TEST_ARGS_NAMESPACE), self.TEST_HTML)

    @responses.activate
    @mock.patch('main.error_reporting.Client.report')
    def test_get_html_raises_exception_on_error_code(self, mock_err_report):
        """
        Test the function performs the GET request which raises an exception on error codes (4xx/5xx).
        When the exception is raised, a report is sent to Google Cloud Error Reporting
        """
        mock_err_report.message = 'test error msg'
        url_to_get = 'https://unreachable.craigslist.org/search/apa'
        responses.add(method=responses.GET, url=url_to_get, status=400, body=requests.exceptions.RequestException())
        self.assertEqual(main.get_html(url_to_get=url_to_get, args=self.TEST_ARGS_NAMESPACE), '')

    def test_get_random_user_agent(self):
        """
        Test a UserAgent string is returned
        """
        self.assertIsInstance(main.get_random_user_agent(), str)

    # TODO: FakeUserAgentError is not raised. Random user agent is returned instead of default
    # @mock.patch('fake_useragent.UserAgent')
    # def test_get_random_user_agent_on_exception(self, mock_random_user_agent):
    #     """
    #     Test a default UserAgent is returned when the FakeUserAgent service is down
    #     """
    #
    #     mock_random_user_agent().side_effect = FakeUserAgentError()
    #     default_random_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 '\
    #                                 '(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'
    #     self.assertEqual(main.get_random_user_agent(), default_random_user_agent)

    def test_parse_window_datetime_start_with_correctly_formatted_str(self):
        """
        Test using valid datetime argument format
        """
        window_datetime_start = datetime.datetime.strptime(self.TEST_WINDOW_DATETIME_START, '%Y-%m-%d %H:%M')
        self.assertEqual(main.parse_custom_datetime(self.TEST_WINDOW_DATETIME_START), window_datetime_start)

    def test_parse_window_datetime_start_raises_error_with_incorrectly_formatted_str(self):
        """
        Test invalid datetime argument raises ValueError
        """
        incorrectly_formatted_datetime_str = '2020-01-01 00:00:00'
        with self.assertRaises(ValueError):
            main.parse_custom_datetime(incorrectly_formatted_datetime_str)

    def test_datetime_in_window_returns_true(self):
        """
        Test with datetime in window returns true
        """
        dt_start = datetime.datetime(2020, 1, 1, 0, 0)  # 2020-01-01 00:00
        dt_end = datetime.datetime(2020, 1, 1, 1, 0)  # 2020-01-01 01:00
        dt_to_check = datetime.datetime(2020, 1, 1, 0, 30)  # 2020-01-01 00:30
        self.assertTrue(main.datetime_in_window(dt_start, dt_end, dt_to_check))

    def test_datetime_in_window_returns_false(self):
        """
        Test with datetime out of window returns false
        """
        dt_start = datetime.datetime(2020, 1, 1, 0, 0)  # 2020-01-01 00:00
        dt_end = datetime.datetime(2020, 1, 1, 1, 0)  # 2020-01-01 01:00
        dt_to_check = datetime.datetime(2020, 1, 1, 1, 30)  # 2020-01-01 01:30
        self.assertFalse(main.datetime_in_window(dt_start, dt_end, dt_to_check))

    def test_extract_posts_in_window(self):
        """
        Test function can extract posts from list that are in the window provided
        """
        posts = self.TEST_SOUP.find_all('li', class_='result-row')
        posts_time_tags = self.TEST_SOUP.find_all('time')
        posted_at_datetimes = [datetime.datetime.strptime(p['datetime'], '%Y-%m-%d %H:%M') for p in posts_time_tags]
        min_posted_at_datetime = min(posted_at_datetimes)  # evaluates to `datetime.datetime(2020, 5, 24, 19, 37)`
        max_posted_at_datetime = max(posted_at_datetimes)  # evaluates to `datetime.datetime(2020, 5, 24, 20, 54)`

        # Round down to nearest hours to create a window of 2020-05-24 19:00-20:00
        dt_start = min_posted_at_datetime.replace(minute=0)  # evaluates to `datetime.datetime(2020, 5, 24, 19, 00)`
        dt_end = max_posted_at_datetime.replace(minute=0)  # evaluates to `datetime.datetime(2020, 5, 24, 20, 00)`

        expected = [p
                    for p in posts
                    if dt_start <= datetime.datetime.strptime(p.find('time')['datetime'], '%Y-%m-%d %H:%M') <= dt_end]

        self.assertListEqual(main.extract_posts_in_window(posts, dt_start, dt_end), expected)

    def test_extract_info_from_post_no_repost(self):
        """
        Test data can be extracted from a post that is not a repost
        """
        post = self.TEST_SOUP.find('li', {'data-repost-of': False}, class_='result-row')
        expected = {
            'href': post.find('a', class_='result-title hdrlnk')['href'],
            'data_id': post.find('a', class_='result-title hdrlnk')['data-id'],
            'posted_at': post.find('time', class_='result-date')['datetime'],
            'repost_of': post.get('data-repost-of')
        }
        self.assertDictEqual(main.extract_info_from_post(post), expected)

    def test_extract_info_from_post_with_repost(self):
        """
        Test data can be extracted from a post that is a repost
        """
        post = self.TEST_SOUP.find('li', {'data-repost-of': True}, class_='result-row')
        expected = {
            'href': post.find('a', class_='result-title hdrlnk')['href'],
            'data_id': post.find('a', class_='result-title hdrlnk')['data-id'],
            'posted_at': post.find('time', class_='result-date')['datetime'],
            'repost_of': post.get('data-repost-of')
        }
        self.assertDictEqual(main.extract_info_from_post(post), expected)

    @responses.activate
    def test_send_post_to_cloud_function(self):
        """
        Test function performs POST request to Google Cloud Function Endpoint
        """
        responses.add(method=responses.POST, url=self.TEST_CLOUD_FN_ENDPOINT, status=201, body=json.dumps(""))
        post = self.TEST_SOUP.find('li', class_='result-row')
        self.assertEqual(main.send_post_to_cloud_function(post, self.TEST_CLOUD_FN_ENDPOINT), ('""', 201))
