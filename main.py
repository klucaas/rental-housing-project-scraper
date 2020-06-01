from google.cloud import error_reporting
from fake_useragent import UserAgent, FakeUserAgentError
from templates import HEADERS, CL_PARAMS
import argparse
import requests
import datetime
import random
import time
import bs4
import sys
import re

err_client = error_reporting.Client()


def parse_args(args: list) -> argparse.Namespace:
    """
    Parse the command line arguments at sys.argv[1:]

    :type args: list
    :param args: command line arguments

    :rtype: argparse.Namespace
    :return: parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--location', type=str, required=True)
    parser.add_argument('--window_datetime_start', type=str, required=True)
    parser.add_argument('--window_length_hours', type=int, required=True)
    parser.add_argument('--cloud_function_endpoint', type=str, required=True)

    return parser.parse_args(args)


def get_random_user_agent() -> str:
    """
    Return a random user agent to include in `get_html` headers. When the FakeUserAgent service is unavailable
    (exception `FakeUserAgentError` is raised) then use default UserAgent.

    :rtype: str
    :return: a userAgent str

    :raises: :class:`FakeUserAgentError` if the resource is unavailable
    """
    random_user_agent = ''
    try:
        user_agent = UserAgent()
        random_user_agent = user_agent.random
    except FakeUserAgentError:
        random_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 '\
                            '(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'
    return random_user_agent


def validate_url(url_to_check: str):
    """
    Validate the URL by testing it against the regex pattern

    :type: str
    :param url_to_check: the url to check against

    :raises: :class:`ValueError` if the URL doesn't match the regex pattern
    """

    regex = r'^https:\/\/\w+\.craigslist\.org\/search\/apa$'
    if not bool(re.match(regex, url_to_check)):
        raise ValueError(f'{url_to_check} is not valid. Please check formatting of location argument.')


def get_headers(args: argparse.Namespace) -> dict:
    """
    Copy HEADERS template, update values for `User-Agent`, `Host`, `Referer`, return formatted headers

    :type args: argpase.Namespace
    :param args: arguments parsed from command line

    :rtype: dict
    :returns: The updated HEADERS
    """
    headers = HEADERS.copy()
    headers.update({
        'Host': f'{args.location}.craigslist.org',
        'Referer': f'https://www.google.com',
        'User-Agent': get_random_user_agent(),
    })
    return headers


def get_html(url_to_get: str, args: argparse.Namespace, **kwargs) -> str:
    """
    Make the GET request, return the response text. Report any errors to Google Cloud Error reporting.

    :type url_to_get: str
    :param url_to_get: The URL to request

    :type args: argparse.Namespace
    :param args: command line arguments

    :rtype: str
    :return:
    """
    response = None
    response_str = ''

    headers = get_headers(args)

    try:
        response = requests.get(url=url_to_get, headers=headers, params=kwargs.get('params', None))
        response.raise_for_status()
        response_str = response.text
    except requests.exceptions.RequestException as err:
        status_code = response.status_code if response else None
        request_context = error_reporting.HTTPContext(
            method='GET', url=url_to_get, user_agent=headers['User-Agent'],
            referrer=headers['Referer'], response_status_code=status_code)
        err_client.report(message=str(err), http_context=request_context)

    return response_str


def parse_custom_datetime(datetime_str: str) -> datetime.datetime:
    """
    Parse a datetime string in format 'YYYY-mm-dd HH:MM'

    :type datetime_str: str
    :param datetime_str: datetime string to parse

    :rtype: datetime.datetime
    :return dt: parsed datetime object

    :raises: :class:`ValueError` if the datetime cannot be parsed (datetime not in correct format)
    """
    try:
        dt = datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
    except ValueError:
        raise ValueError('window_datetime_start is incorrectly formatted. Correct format is: YYYY-MM-DD HH:MM')

    return dt


def datetime_in_window(dt_start: datetime.datetime, dt_end: datetime.datetime, dt_to_check: datetime.datetime) -> bool:
    """
    Check if a datetime is in range [dt_start, dt_end]

    :type dt_start: datetime.datetime
    :param dt_start: window start datetime

    :type dt_end: datetime.datetime
    :param dt_end: window end datetime

    :type dt_to_check: datetime.datetime
    :param dt_to_check: datetime to check

    :rtype: bool
    :return: True when in range, otherwise false
    """
    if dt_start <= dt_to_check <= dt_end:
        return True

    return False


def extract_posts_in_window(page_posts: list, dt_start: datetime.datetime, dt_end: datetime.datetime) -> list:
    """
    Filter posts not in range[dt_start, dt_end]

    :type page_posts: list
    :param page_posts: posts extracted from a URL

    :type dt_start: datetime.datetime
    :param dt_start: window start datetime

    :type dt_end: datetime.datetime
    :param dt_end: window end datetime

    :rtype: list
    :return: posts in range[dt_start, dt_end]
    """
    return [post
            for post in page_posts
            if datetime_in_window(dt_start, dt_end, parse_custom_datetime(post.time['datetime']))]


def extract_info_from_post(post: bs4.element.Tag) -> dict:
    """
    Extract attributes of interest from tags within a single post

    :type post: bs4.element.Tag
    :param post: a HTML Tag representing a single post

    :rtype: dict
    :return: dict containing the data extracted
    """
    result_title_tag = post.find('a', class_='result-title hdrlnk')
    href = result_title_tag.get('href')
    data_id = result_title_tag.get('data-id')
    time_tag = post.find('time', class_='result-date')
    posted_at = time_tag.get('datetime')
    repost_of = post.get('data-repost-of')

    return {
        'href': href,
        'data_id': data_id,
        'posted_at': posted_at,
        'repost_of': repost_of
    }


def send_post_to_cloud_function(post: bs4.element.Tag, cloud_fn_endpoint: str) -> tuple:
    """
    Perform a POST request to a Google Cloud Function endpoint. Space out the requests by introducing
    a pause between POSTs

    :type post: bs4.element.Tag
    :param post: a HTML Tag representing a single post

    :type cloud_fn_endpoint: str
    :param cloud_fn_endpoint: cloud function endpoint to POST to

    :rtype: tuple
    :return: (data, status)
    """
    time.sleep(random.randint(5, 20))
    data = extract_info_from_post(post)
    response = requests.post(url=cloud_fn_endpoint, json=data)
    return response.text, response.status_code


if __name__ == '__main__':
    arguments = parse_args(sys.argv[1:])
    window_datetime_start = parse_custom_datetime(arguments.window_datetime_start)
    window_datetime_end = window_datetime_start + datetime.timedelta(hours=arguments.window_length_hours)
    url = f'https://{arguments.location}.craigslist.org/search/apa'
    validate_url(url)
    soup = bs4.BeautifulSoup(get_html(url, params=CL_PARAMS, args=arguments), 'html.parser')
    posts = soup.find_all('li', class_='result-row')
    posts_in_window = extract_posts_in_window(posts, window_datetime_start, window_datetime_end)
    map_iterator = map(lambda post: send_post_to_cloud_function(post, arguments.cloud_function_endpoint), posts_in_window)
    results = list(map_iterator)
    # TODO: Do something with results such as record (status_code == 201 / status_code != 201) * 100 as success rate

