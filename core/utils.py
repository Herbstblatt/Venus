from typing import Optional, Union
from urllib.parse import ParseResult, parse_qs, urlparse


def has_flag(value, flag):
    return value & flag == flag

def extract_query_param(url: Union[str, ParseResult], param: str) -> Optional[str]:
    if isinstance(url, str):
        url = urlparse(url)
    return parse_qs(url.query).get(param, [None])[0]