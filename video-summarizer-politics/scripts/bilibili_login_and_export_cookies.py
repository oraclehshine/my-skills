#!/usr/bin/env python3
"""
Open the Bilibili login page in a browser, wait for the user to sign in,
then export the current Bilibili cookies into a Netscape cookies.txt file.
"""

from __future__ import annotations

import argparse
import sys
import time
import webbrowser
from http.cookiejar import CookieJar
from pathlib import Path


LOGIN_URL = "https://passport.bilibili.com/login"


def load_cookiejar(browser: str) -> CookieJar:
    try:
        import browser_cookie3  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'browser-cookie3'. Install it with: pip install browser-cookie3"
        ) from exc

    browser = browser.lower()
    if browser == "chrome":
        return browser_cookie3.chrome(domain_name="bilibili.com")
    if browser == "edge":
        return browser_cookie3.edge(domain_name="bilibili.com")
    raise RuntimeError(f"Unsupported browser: {browser}")


def open_login_page() -> None:
    webbrowser.open(LOGIN_URL, new=2)


def has_session_cookie(cookiejar: CookieJar) -> bool:
    required = {"SESSDATA", "bili_jct", "DedeUserID"}
    seen = {cookie.name for cookie in cookiejar}
    return required.issubset(seen)


def to_netscape_line(cookie) -> str:
    domain = cookie.domain or ".bilibili.com"
    include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
    path = cookie.path or "/"
    secure = "TRUE" if cookie.secure else "FALSE"
    expires = str(int(cookie.expires or 0))
    return "\t".join(
        [
            domain,
            include_subdomains,
            path,
            secure,
            expires,
            cookie.name,
            cookie.value,
        ]
    )


def write_cookie_file(cookiejar: CookieJar, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bilibili_cookies = [cookie for cookie in cookiejar if "bilibili.com" in (cookie.domain or "")]
    lines = ["# Netscape HTTP Cookie File"]
    lines.extend(to_netscape_line(cookie) for cookie in bilibili_cookies)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(bilibili_cookies)


def wait_for_login(browser: str, timeout: int, interval: float) -> CookieJar:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            cookiejar = load_cookiejar(browser)
            if has_session_cookie(cookiejar):
                return cookiejar
        except Exception as exc:  # pragma: no cover
            last_error = exc
        time.sleep(interval)
    if last_error:
        raise RuntimeError(f"Failed to read browser cookies: {last_error}")
    raise RuntimeError("Timed out waiting for a valid Bilibili login session.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open Bilibili login page and export cookies for later downloads."
    )
    parser.add_argument(
        "--browser",
        default="chrome",
        choices=["chrome", "edge"],
        help="Browser profile to read cookies from.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write Netscape cookies.txt file.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="How long to wait for the user to finish login, in seconds.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Polling interval when checking the browser cookie store.",
    )
    args = parser.parse_args()

    print(f"Opening Bilibili login page in {args.browser}...")
    open_login_page()
    print("Please finish login in the browser window. Waiting for cookies...")

    cookiejar = wait_for_login(args.browser, args.timeout, args.interval)
    output_path = Path(args.output)
    count = write_cookie_file(cookiejar, output_path)

    print(f"Exported {count} cookies to {output_path}")
    print("You can now reuse this file with download.py --cookies <path>.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
