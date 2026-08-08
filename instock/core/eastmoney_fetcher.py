#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
import time
import random
import logging
from instock.core.singleton_proxy import proxys

try:
    from curl_cffi import requests as curl_requests
    from curl_cffi.requests.exceptions import RequestException as CurlRequestException
    from curl_cffi import CurlOpt
except ImportError:  # 允许旧环境先以 requests 运行，但 push2 的成功率会较低。
    curl_requests = None
    CurlRequestException = ()
    CurlOpt = None

__author__ = 'myh '
__date__ = '2025/12/31 '

class eastmoney_fetcher:
    """
    东方财富网数据获取器
    封装了Cookie管理、会话管理和请求发送功能
    """

    def __init__(self):
        """初始化获取器"""
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.proxies = proxys().get_proxies()
        # 如果未配置代理文件，默认禁用系统代理 (避免本地 Clash/V2Ray 等 7897 代理端口拦截东方财富接口)
        if not self.proxies:
            self.proxies = {"http": None, "https": None}
        # 仅对东财开放显式代理出口；不读取 HTTP(S)_PROXY，以免被系统代理劫持。
        eastmoney_proxy = os.environ.get('EASTMONEY_PROXY', '').strip()
        self.eastmoney_proxies = (
            {"http": eastmoney_proxy, "https": eastmoney_proxy}
            if eastmoney_proxy else {"http": None, "https": None}
        )
        self.session = self._create_session()

    def _get_cookie(self):
        """
        获取东方财富网的Cookie
        优先级：环境变量 > 文件 > 默认Cookie
        """
        # 1. 尝试从环境变量获取
        cookie = os.environ.get('EAST_MONEY_COOKIE')
        if cookie:
            return cookie

        # 2. 尝试从文件获取
        cookie_file = Path(os.path.join(self.base_dir, 'config', 'eastmoney_cookie.txt'))
        if cookie_file.exists():
            with open(cookie_file, 'r') as f:
                cookie = f.read().strip()
            if cookie:
                return cookie

        # 3. 默认Cookie（仅作为备选）
        return 'st_si=78948464251292; st_psi=20260205091253851-119144370567-1089607836; st_pvi=07789985376191; st_sp=2026-02-05%2009%3A11%3A13; st_inirUrl=https%3A%2F%2Fxuangu.eastmoney.com%2FResult; st_sn=12; st_asi=20260205091253851-119144370567-1089607836-webznxg.dbssk.qxg-1'

    def _create_session(self, connection_close=False):
        """创建并配置会话"""
        session = requests.Session()
        # 禁止 requests 自动读取系统代理环境变量，避免被本机代理劫持到不可用链路
        session.trust_env = False
        session.proxies = {"http": None, "https": None}

        # 配置连接池
        retry_strategy = Retry(
            total=1,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"]
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=50,  # 增加连接池大小
            pool_maxsize=50  # 增加连接池最大大小
        )

        # 为http和https请求添加适配器
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # 设置请求头
        cookie_str = self._get_cookie()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://quote.eastmoney.com/',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            # push2 会主动关闭复用过多的连接。调用方可为这类请求明确禁用复用。
            'Connection': 'close' if connection_close else 'keep-alive',
        }
        if cookie_str:
            headers['Cookie'] = cookie_str
        session.headers.update(headers)
        return session

    def _get_real_ip(self, host):
        """HTTP DNS 自动解析真实 IP (绕过 Clash TUN Fake-IP)"""
        try:
            r = requests.get(f'https://dns.alidns.com/resolve?name={host}&type=A', proxies={'http': None, 'https': None}, timeout=3)
            for item in r.json().get('Answer', []):
                if item.get('type') == 1:
                    ip = item.get('data')
                    if ip and not ip.startswith('198.18.') and not ip.endswith('.'):
                        return ip
        except Exception:
            pass
        return None

    def make_request(self, url, params=None, retry=3, timeout=10):
        """
        发送请求
        :param url: 请求URL
        :param params: 请求参数
        :param retry: 重试次数
        :param timeout: 超时时间
        :return: 响应对象
        """
        if url.startswith('http://push2'):
            url = url.replace('http://push2', 'https://push2', 1)
        if url.startswith('http://push2his'):
            url = url.replace('http://push2his', 'https://push2his', 1)

        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.netloc.split(':')[0]

        # 东财的实时行情服务有多个等价入口。某个 CDN 节点断开连接时，按重试次数
        # 轮换节点；不要把 "82.push2" 等入口改写回 push2，否则容错不会生效。
        push2_hosts = ('push2.eastmoney.com', '82.push2.eastmoney.com', '79.push2.eastmoney.com')
        request_urls = (
            [url.replace(host, candidate, 1) for candidate in push2_hosts]
            if host == 'push2.eastmoney.com' else [url]
        )
        for i in range(retry):
            request_url = request_urls[i % len(request_urls)]
            request_host = urlparse(request_url).netloc.split(':')[0]
            cookie_str = self._get_cookie()
            direct_headers = {
                'Host': request_host,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://quote.eastmoney.com/',
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
            }
            if cookie_str:
                direct_headers['Cookie'] = cookie_str

            # push2 会校验客户端 TLS/HTTP 指纹。curl_cffi 使用 Chrome 指纹和 HTTP/2，
            # 同时保持独立会话，避免复用服务端已关闭的连接。显式清空 libcurl
            # 读取到的系统代理；若配置 EASTMONEY_PROXY，下面的 proxy 参数会覆盖它。
            is_push2 = (
                request_host == 'push2.eastmoney.com'
                or request_host.endswith('.push2.eastmoney.com')
            )
            use_chrome_transport = is_push2 and curl_requests is not None
            use_fresh_session = is_push2 and not use_chrome_transport
            request_proxies = self.eastmoney_proxies if request_host.endswith('.eastmoney.com') else {"http": None, "https": None}
            request_session = (
                curl_requests.Session(
                    impersonate='chrome',
                    trust_env=False,
                    # push2 对部分 HTTP/2 指纹会在握手后直接断开；Chrome 指纹配合
                    # HTTP/1.1 更接近网页首屏所使用的兼容链路。
                    http_version='v1',
                    curl_options={CurlOpt.PROXY: ''} if CurlOpt is not None and not request_proxies.get('https') else None,
                )
                if use_chrome_transport else
                self._create_session(connection_close=True) if use_fresh_session else self.session
            )
            try:
                if use_chrome_transport:
                    # 不覆盖 curl_cffi 生成的 Chrome UA、TLS 和 HTTP/2 头；仅提供
                    # 东财所需的来源、语言和登录 Cookie。
                    chrome_headers = {
                        key: value for key, value in direct_headers.items()
                        if key in {'Accept', 'Accept-Language', 'Referer', 'Cookie'}
                    }
                    response = request_session.get(
                        request_url,
                        params=params,
                        headers=chrome_headers,
                        proxy=request_proxies.get('https'),
                        timeout=timeout,
                    )
                else:
                    response = request_session.get(
                        request_url,
                        proxies=request_proxies,
                        params=params,
                        headers=direct_headers,
                        timeout=timeout
                    )
                response.raise_for_status()  # 检查HTTP错误
                return response
            except (requests.exceptions.RequestException, CurlRequestException) as e:
                logging.warning(
                    "eastmoney_fetcher.make_request会话请求失败: host=%s try=%s/%s error=%s",
                    request_host,
                    i + 1,
                    retry,
                    e,
                )
                if i < retry - 1:
                    time.sleep(random.uniform(1, 2))
                else:
                    raise
            finally:
                if use_fresh_session or use_chrome_transport:
                    request_session.close()

    def make_post_request(self, url, data=None, json=None, params=None, retry=3, timeout=60):
        """
        发送POST请求
        :param url: 请求URL
        :param data: 请求数据（表单形式）
        :param json: 请求数据（JSON形式）
        :param params: URL参数
        :param retry: 重试次数
        :param timeout: 超时时间
        :return: 响应对象
        """
        for i in range(retry):
            try:
                response = self.session.post(
                    url,
                    proxies={"http": None, "https": None},
                    params=params,
                    data=data,
                    json=json,
                    timeout=timeout
                )
                response.raise_for_status()  # 检查HTTP错误
                return response
            except requests.exceptions.RequestException as e:
                print(f"请求错误: {e}, 第 {i + 1}/{retry} 次重试")
                if i < retry - 1:
                    # 随机延迟后重试
                    time.sleep(random.uniform(1, 3))
                else:
                    raise

    def update_cookie(self, new_cookie):
        """
        更新Cookie
        :param new_cookie: 新的Cookie值
        """
        self.session.cookies.update({'Cookie': new_cookie})
