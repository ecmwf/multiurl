import logging
import time

import requests

LOG = logging.getLogger(__name__)

RETRIABLE = (
    requests.codes.internal_server_error,
    requests.codes.bad_gateway,
    requests.codes.service_unavailable,
    requests.codes.gateway_timeout,
    requests.codes.too_many_requests,
    requests.codes.request_timeout,
)


def _logged_sleep(seconds):
    LOG.warning(f"Retrying in {seconds} seconds")
    time.sleep(seconds)


def robust(
    call,
    maximum_tries=500,
    retry_after=120,
    mirrors=None,
    use_server_retry_after=False,
):
    def retriable(code):
        return code in RETRIABLE

    def wrapped(url, *args, **kwargs):
        tries = 0
        main_url = url

        if isinstance(retry_after, (list, tuple)):
            sleep_min, sleep_max, sleep_incremental_ratio = retry_after
        elif isinstance(retry_after, (int, float)):
            sleep_min = sleep_max = retry_after
            sleep_incremental_ratio = 1
        else:
            raise TypeError("retry_after must be int, float, tuple, or list")

        assert sleep_min >= 0 and sleep_incremental_ratio > 0
        assert (
            sleep_min == sleep_max
            if sleep_incremental_ratio == 1
            else sleep_min < sleep_max
        )
        sleep = sleep_min if sleep_incremental_ratio >= 1 else sleep_max

        while True:
            tries += 1

            if tries >= maximum_tries:
                # Last attempt, don't do anything
                return call(main_url, *args, **kwargs)

            try:
                r = call(main_url, *args, **kwargs)
            except requests.exceptions.SSLError:
                raise
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.ChunkedEncodingError,
            ) as e:
                r = None
                LOG.warning(
                    "Recovering from connection error [%s], attempt %s of %s",
                    e,
                    tries,
                    maximum_tries,
                )

            if r is not None:
                if not retriable(r.status_code):
                    return r
                LOG.warning(
                    "Recovering from HTTP error [%s %s], attempt %s of %s",
                    r.status_code,
                    r.reason,
                    tries,
                    maximum_tries,
                )

            alternate = None
            replace = 0
            if mirrors is not None:
                for key, values in mirrors.items():
                    if url.startswith(key):
                        alternate = values
                        replace = len(key)
                        if not isinstance(alternate, (list, tuple)):
                            alternate = [alternate]

            if alternate is not None:
                mirror = random.choice(alternate)
                LOG.warning("Retrying using mirror %s", mirror)
                main_url = f"{mirror}{url[replace:]}"
            else:
                server_sleep = None
                if (
                    use_server_retry_after
                    and r is not None
                    and "retry-after" in r.headers
                ):
                    try:
                        server_sleep = float(r.headers["retry-after"])
                    except ValueError:
                        pass

                if server_sleep is not None:
                    _logged_sleep(server_sleep)
                else:
                    _logged_sleep(sleep)
                    sleep = (
                        min(sleep * sleep_incremental_ratio, sleep_max)
                        if sleep_incremental_ratio >= 1
                        else max(sleep_min, sleep * sleep_incremental_ratio)
                    )
                LOG.info("Retrying now...")

    return wrapped
