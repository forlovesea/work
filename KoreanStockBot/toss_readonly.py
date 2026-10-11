"""Official OAuth connectivity check only; never places orders or prints secrets."""
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = 'https://openapi.tossinvest.com'


def check_connection():
    client_id = os.environ.get('TOSS_CLIENT_ID', '')
    secret = os.environ.get('TOSS_CLIENT_SECRET', '')
    if not client_id or not secret:
        raise ValueError('TOSS_CLIENT_ID, TOSS_CLIENT_SECRET 환경변수를 로컬에서 설정하세요.')
    request = Request(BASE+'/oauth2/token', data=urlencode(dict(
        grant_type='client_credentials', client_id=client_id, client_secret=secret)).encode(),
        headers={'Content-Type':'application/x-www-form-urlencoded'}, method='POST')
    with urlopen(request, timeout=15) as response:
        token = json.load(response)['access_token']
    # Public stock metadata only; account/order endpoints are intentionally absent.
    request = Request(BASE+'/api/v1/stocks?symbols=005930',headers={'Authorization':'Bearer '+token})
    with urlopen(request,timeout=15) as response:
        json.load(response)
    return '인증 및 종목정보 조회 성공. 실제 주문은 전송하지 않았습니다.'


if __name__ == '__main__':
    try:
        print(check_connection())
    except HTTPError as exc:
        print(f'API 오류 HTTP {exc.code}. 키/허용 IP/서비스 권한을 확인하세요.')
        raise SystemExit(1)
    except (ValueError, KeyError, URLError, TimeoutError):
        print('연결 실패: 환경변수, 네트워크 또는 API 응답을 확인하세요. 비밀키를 공유하지 마세요.')
        raise SystemExit(1)
