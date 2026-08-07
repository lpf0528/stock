#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
import time
import random
from instock.core.singleton_proxy import proxys

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

    def _create_session(self):
        """创建并配置会话"""
        session = requests.Session()

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
            'Connection': 'keep-alive',
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
        return '47.112.165.11'

    def make_request(self, url, params=None, retry=3, timeout=10):
        """
        发送请求
        :param url: 请求URL
        :param params: 请求参数
        :param retry: 重试次数
        :param timeout: 超时时间
        :return: 响应对象
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.netloc.split(':')[0]

        # 构造直连 Headers 绕过 Clash TUN Fake-IP (198.18.x.x)
        cookie_str = self._get_cookie()
        direct_headers = {
            'Host': host,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://quote.eastmoney.com/',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
        }
        if cookie_str:
            direct_headers['Cookie'] = cookie_str

        real_ip = self._get_real_ip(host)
        if real_ip:
            direct_url = url.replace(host, real_ip, 1)
            for i in range(retry):
                try:
                    resp = requests.get(direct_url, params=params, headers=direct_headers, proxies={'http': None, 'https': None}, timeout=timeout)
                    if resp.status_code == 200:
                        return resp
                except Exception:
                    pass
                time.sleep(0.5)

        for i in range(retry):
            try:
                response = self.session.get(
                    url,
                    proxies=self.proxies,
                    params=params,
                    timeout=timeout
                )
                response.raise_for_status()  # 检查HTTP错误
                return response
            except requests.exceptions.RequestException:
                if i < retry - 1:
                    time.sleep(random.uniform(1, 2))
                else:
                    raise

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
                    proxies=self.proxies,
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
