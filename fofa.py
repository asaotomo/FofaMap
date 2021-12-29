import configparser
import base64
import json
import urllib
import urllib.request
import urllib.parse
import ssl


class Client:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('fofa.ini', encoding="utf-8")
        self.email = config.get("userinfo", "email")
        self.key = config.get("userinfo", "key")
        self.base_url = "https://fofa.so"
        self.search_api_url = "/api/v1/search/all"
        self.login_api_url = "/api/v1/info/my"
        self.get_userinfo()  # check email and key

    def get_userinfo(self):
        api_full_url = "%s%s" % (self.base_url, self.login_api_url)
        param = {"email": self.email, "key": self.key}
        res = self.__http_get(api_full_url, param)
        return json.loads(res)

    def get_data(self, query_str, page=1, fields=""):
        res = self.get_json_data(query_str, page, fields)
        return json.loads(res)

    def get_json_data(self, query_str, page=1, fields=""):
        api_full_url = "%s%s" % (self.base_url, self.search_api_url)
        param = {"qbase64": base64.b64encode(bytes(query_str.encode('utf-8'))), "email": self.email, "key": self.key,
                 "page": page,
                 "fields": fields}
        res = self.__http_get(api_full_url, param)
        return res

    def __http_get(self, url, param):
        ssl._create_default_https_context = ssl._create_unverified_context
        param = urllib.parse.urlencode(param)
        url = "%s?%s" % (url, param)
        try:
            req = urllib.request.Request(url)
            res = urllib.request.urlopen(req).read().decode('utf-8')
            if "errmsg" in res:
                raise RuntimeError(res)
        except Exception as e:
            raise e
        return res
