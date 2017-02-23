import os
import pycurl

__author__ = 'rhuberdeau'


def curl_post_data(api_endpoint, filename, logger):
    c = pycurl.Curl()
    c.setopt(c.URL, api_endpoint)
    c.setopt(c.UPLOAD, True)
    c.setopt(c.VERBOSE, True)
    c.setopt(pycurl.CONNECTTIMEOUT, 5)
    c.setopt(pycurl.TIMEOUT, 5)
    c.setopt(pycurl.READFUNCTION, open(filename, 'rb').read)
    c.setopt(pycurl.INFILESIZE, os.path.getsize(filename))

    try:
        c.perform()
        response_code = c.getinfo(c.RESPONSE_CODE)
        logger.debug("CODE == {code}".format(code=response_code))

        if response_code != 200:
            logger.error("CODE == {code}".format(code=response_code))
    except pycurl.error as e:
        logger.error("Pycurl error: " + str(e))
    except Exception as e:
        logger.error("curl error: " + str(e))
    finally:
        c.close()
