#!/usr/bin/env python3
# 生成「视频设备运维一张图·公开版」并推送到 GitHub：
# 读取内部源码（本文件上级目录 = shipin_app），剥离天地图真实密钥，注入公开版元信息，
# 经 REST 内容 API 幂等推送。内部版密钥永不进入公开库。
# 背景：本机不通 github.com:443，仅 api.github.com REST 可达，故用内容 API 推送。
# 用法：python build/push_public.py
import os, sys, base64, json, re, hashlib, subprocess, time, http.client, urllib.request, urllib.error, urllib.parse

# 公开版仓库（g101400 账号下，公开）
REPO_PUBLIC = 'g101400/shipin-public-4060'
# 内部源码根：本文件位于 <repo>/build/push_public.py，上级目录即 shipin_app 根
INTERNAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ===== 注入公开版的元信息（不来自内部源码，单独维护）=====
PUB_GITIGNORE = """# ===== 密钥（本地真实值，绝不入库）=====
secrets/config.local.js
# 安卓签名 keystore（发布签名凭据，本地持有；公开库仅放路径引用）
build/targets/keystore/
build/targets/android/local.properties
build/targets/*/.gradle/

# ===== 构建产物 / 安装包 =====
*.apk
*.aab
*.ipa
*.deb
*.exe
*.msi
*.zip
releases/
build_v24*.log
.build_v24_ts
.upload_tmp
.upload_tmp.done
dist/
out/
build/targets/*/node_modules/
build/targets/*/release*/
build/targets/*/.ecache/
build/targets/*/.npmcache/
build/targets/win11/jingmi_app/*
build/targets/uos/jingmi_app/*
build/targets/android/app/src/main/assets/www/*
build/targets/android/app/build/
build/targets/android/.gradle/
build/targets/ios/*/pwa/*

# ===== 备份 / 日志 / 临时 =====
*.bak
*.bak*
*.log
.data.real.*
*.apk_hold
rel_extract*/

# ===== 依赖 / 工具 =====
node_modules/
.thumbs/
.DS_Store
Thumbs.db
*.swp
*.swo
"""

PUB_CONFIG_JS = """// 提交的占位配置模板（已入库）。真实密钥见同目录 config.local.js（本地，.gitignore 排除）。
// 加载顺序：index.html 先加载 config.local.js（若存在则覆盖下方值），再加载本文件只做兜底填充。
// 克隆仓库且无 config.local.js 时，下方为空占位——应用内地图底图不会加载，直到你填入真实 token。
window.__CONFIG__ = window.__CONFIG__ || {
  TIANDITU_TOKEN: "",
  TIANDITU_SERVER_TOKEN: ""
};
"""

PUB_README = """# 视频设备运维一张图（公开版）

一张图家族 APP —— 视频设备运维一张图（感知设备一张图）对外公开发行版本。基于 PWA，支持 Windows / UOS / Android / iOS 四端，内置地图、设备台账、知识库、网盘导入导出等能力。

> ⚠️ 本仓库为**公开版**：天地图密钥已在提交中剥离（`js/app.js` 的 `TIANDITU_DEFAULT` 置空、`index.html` 不再内联 token）。克隆后地图底图不会自动加载，需自行配置密钥。

## 配置天地图密钥（二选一）

1. **本地密钥文件（推荐，不入库）**：在本目录新建 `secrets/config.local.js`：

   ```js
   window.__CONFIG__ = {
     TIANDITU_TOKEN: "你的浏览器端token",
     TIANDITU_SERVER_TOKEN: "你的服务端token"
   };
   ```

   `index.html` 会优先加载它覆盖占位值。

2. **应用内设置**：打开应用 → 设置 → 天地图密钥管理，手动填入并保存（写入浏览器 localStorage，等效）。

## 目录

- `index.html` / `js/` / `css/` / `lib/`：前端应用
- `data.js` / `data.json`：地图与台账数据
- `build/`：构建与同步脚本
- `secrets/`：密钥占位（`config.js` 已提交，`config.local.js` 本地持有，勿提交）

## 同步到 GitHub

本仓库通过 GitHub REST 内容 API 推送（本机不通 git 协议）。本地更新后运行：

```bash
python build/push.py
```

内部版（含真实密钥，私有）：`shipin-internal-4060`。
"""

PUB_PUSH_PY = """#!/usr/bin/env python3
# 视频设备运维一张图（公开版）自包含同步脚本：将本仓库当前内容幂等推送回 GitHub。
# 注意：本脚本只做「本仓库内容 -> GitHub」的再同步；若要从内部版重新生成剥离后的公开版，
# 请在内部源码目录运行 build/push_public.py。
import os, sys, base64, json, hashlib, subprocess, time, http.client, urllib.request, urllib.error, urllib.parse

REPO = 'g101400/shipin-public-4060'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_token():
    for k in ('GITHUB_TOKEN', 'GH_TOKEN'):
        v = os.environ.get(k)
        if v:
            return v.strip()
    p = os.environ.get('GITHUB_TOKEN_FILE', r'D:/Users/WorkBuddy/.github_token')
    if os.path.isfile(p):
        return open(p, encoding='utf-8').read().strip()
    sys.exit('未找到 GitHub Token')
TOKEN = load_token()

def api(path, method='GET', data=None, _try=0):
    url = 'https://api.github.com/repos/%s/%s' % (REPO, urllib.parse.quote(path, safe='/,=:'),)
    body = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Authorization', 'Bearer %s' % TOKEN)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('Content-Type', 'application/json')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404, 409, 422):
            return e.code, e.read().decode('utf-8', 'replace')
        if _try < 4:
            time.sleep(2 * (_try + 1))
            return api(path, method, data, _try + 1)
        return e.code, e.read().decode('utf-8', 'replace')
    except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError):
        if _try < 4:
            time.sleep(2 * (_try + 1))
            return api(path, method, data, _try + 1)
        return 0, ''
    except Exception:
        if _try < 4:
            time.sleep(2 * (_try + 1))
            return api(path, method, data, _try + 1)
        return 0, ''

def git_blob_sha(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(b'blob ' + str(len(data)).encode() + b'\\x00' + data)
    return h.hexdigest()

def remote_sha(path):
    st, body = api('contents/%s' % path)
    if st == 200:
        return json.loads(body).get('sha')
    if st == 404:
        return None
    return False

out = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
files = [f for f in out.decode('utf-8').split('\\x00') if f]
added = updated = fail = skip = 0
for f in files:
    p = os.path.join(ROOT, f)
    if not os.path.isfile(p):
        print('SKIP(缺失) %s' % f); skip += 1; continue
    with open(p, 'rb') as fh:
        raw = fh.read()
    b64 = base64.b64encode(raw).decode('ascii')
    ls = git_blob_sha(raw)
    rs = remote_sha(f)
    if rs == ls:
        print('SKIP(未变) %s' % f); skip += 1; continue
    if rs is None:
        st2, body2 = api('contents/%s' % f, 'PUT', {'message': 'add %s' % f, 'content': b64})
        if st2 in (200, 201):
            added += 1; print('ADD  %s' % f)
        else:
            fail += 1; print('FAIL %s -> %s %s' % (f, st2, (json.loads(body2).get('message', '') if body2 else '')[:120]))
    else:
        payload = {'message': 'update %s' % f, 'content': b64}
        if isinstance(rs, str):
            payload['sha'] = rs
        st2, body2 = api('contents/%s' % f, 'PUT', payload)
        if st2 in (200, 201):
            updated += 1; print('UPDATE %s' % f)
        else:
            fail += 1; print('FAIL %s -> %s %s' % (f, st2, (json.loads(body2).get('message', '') if body2 else '')[:120]))
print('\\n完成：新增 %d / 更新 %d / 跳过 %d / 失败 %d / 共 %d' % (added, updated, skip, fail, len(files)))
sys.exit(1 if fail else 0)
"""


def load_token():
    for k in ('GITHUB_TOKEN', 'GH_TOKEN'):
        v = os.environ.get(k)
        if v:
            return v.strip()
    p = os.environ.get('GITHUB_TOKEN_FILE', r'D:/Users/WorkBuddy/.github_token')
    if os.path.isfile(p):
        return open(p, encoding='utf-8').read().strip()
    sys.exit('未找到 GitHub Token')


TOKEN = load_token()


def api(path, method='GET', data=None, _try=0):
    url = 'https://api.github.com/repos/%s/%s' % (REPO_PUBLIC, urllib.parse.quote(path, safe='/,=:'),)
    body = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Authorization', 'Bearer %s' % TOKEN)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('Content-Type', 'application/json')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404, 409, 422):
            return e.code, e.read().decode('utf-8', 'replace')
        if _try < 4:
            time.sleep(2 * (_try + 1))
            return api(path, method, data, _try + 1)
        return e.code, e.read().decode('utf-8', 'replace')
    except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError) as e:
        if _try < 4:
            time.sleep(2 * (_try + 1))
            return api(path, method, data, _try + 1)
        return 0, ''
    except Exception:
        if _try < 4:
            time.sleep(2 * (_try + 1))
            return api(path, method, data, _try + 1)
        return 0, ''


def git_blob_sha(data: bytes) -> str:
    """计算 git blob sha1（与 GitHub 存储的 blob sha 一致），无需下载远端内容即可比对。"""
    h = hashlib.sha1()
    h.update(b'blob ' + str(len(data)).encode() + b'\x00' + data)
    return h.hexdigest()


def remote_sha(path):
    """返回 GitHub 上该文件的 git blob sha。404->None（不存在）；其他错误->False。
    仅取 Contents API 返回的 sha 字段，>1MB 文件也不会触发大体积下载。"""
    st, body = api('contents/%s' % path)
    if st == 200:
        return json.loads(body).get('sha')
    if st == 404:
        return None
    return False


def purge_pycache():
    """删除已推上公开库但应排除的 __pycache__ 垃圾文件。"""
    st, body = api('contents/build/__pycache__')
    if st != 200:
        return
    for it in json.loads(body):
        if it.get('type') == 'file':
            p = 'build/__pycache__/%s' % it['name']
            st2, _ = api('contents/%s' % p, 'DELETE', {'message': 'chore: drop pycache', 'sha': it['sha']})
            print('DEL(清理) %s -> %s' % (p, st2))


def skipped(f):
    """公开版不入库的内容：真实密钥 / 构建产物 / 备份。"""
    low = f.lower()
    if f in ('build/push.py', 'build/push_public.py'):
        return True
    for e in ('.git/', 'node_modules/', 'releases/', 'dist/', 'out/', '.workbuddy/',
              'rel_extract', 'build_v24', '.build_v24_ts', '.upload_tmp', '.ecache', '.npmcache',
              '.data.real.', 'data.public.', 'js/app.public.js', 'secrets/config.local.js'):
        if e in low:
            return True
    if '.bak' in low or '._bak' in low or low.endswith('.bak'):
        return True
    for suf in ('.apk', '.aab', '.ipa', '.deb', '.exe', '.msi', '.zip', '.log'):
        if low.endswith(suf):
            return True
    return False


def strip_appjs(content):
    content = re.sub(r'const TIANDITU_DEFAULT = "[^"]*";', 'const TIANDITU_DEFAULT = "";', content)
    content = re.sub(r'const TIANDITU_SERVER_DEFAULT = "[^"]*";', 'const TIANDITU_SERVER_DEFAULT = "";', content)
    return content


def strip_aijs(content):
    # 移除 OpenRouter 真实 API Key（公开版不携带任何第三方密钥）
    content = re.sub(r'sk-or-v1-[A-Za-z0-9]+', '""', content)
    return content


def strip_index(content):
    # 移除内联 window.__CONFIG__ = {token...} 块（含跨行）
    content = re.sub(r'\n\s*window\.__CONFIG__\s*=\s*\{.*?\};', '', content, flags=re.S)
    inject = ('<!-- 加载密钥：先 config.local.js（本地真实值，若存在则覆盖），再 config.js（占位模板，已入库） -->\n'
              '<script src="secrets/config.local.js"></script>\n'
              '<script src="secrets/config.js"></script>\n')
    content = content.replace('<script src="js/app.js"></script>', inject + '<script src="js/app.js"></script>', 1)
    return content


# 枚举内部源码（排除真实密钥/构建产物）
out = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=INTERNAL)
src_files = [f for f in out.decode('utf-8').split('\x00') if f and not skipped(f)]

to_push = {}  # path -> bytes
for f in src_files:
    p = os.path.join(INTERNAL, f)
    if not os.path.isfile(p):
        continue
    raw = open(p, 'rb').read()
    if f == 'js/app.js' or f == 'js/app.public.js':
        raw = strip_appjs(raw.decode('utf-8')).encode('utf-8')
    elif f == 'js/ai.js' or f == 'js/ai.public.js':
        raw = strip_aijs(raw.decode('utf-8')).encode('utf-8')
    elif f == 'index.html':
        raw = strip_index(raw.decode('utf-8')).encode('utf-8')
    to_push[f] = raw

# 注入公开版元信息（不来自内部源码）
to_push['.gitignore'] = PUB_GITIGNORE.encode('utf-8')
to_push['secrets/config.js'] = PUB_CONFIG_JS.encode('utf-8')
to_push['README.md'] = PUB_README.encode('utf-8')
to_push['build/push.py'] = PUB_PUSH_PY.encode('utf-8')

added = updated = fail = skip = 0
for f, raw in to_push.items():
    b64 = base64.b64encode(raw).decode('ascii')
    # 比对 git blob sha（不下载内容）：不存在则新增；sha 相同则跳过；sha 不同则带 sha 更新
    ls = git_blob_sha(raw)
    rs = remote_sha(f)
    if rs == ls:
        print('SKIP(未变) %s' % f)
        skip += 1
        continue
    if rs is None:
        st2, body2 = api('contents/%s' % f, 'PUT', {'message': 'add %s' % f, 'content': b64})
        if st2 in (200, 201):
            added += 1
            print('ADD  %s' % f)
        else:
            fail += 1
            print('FAIL %s -> %s %s' % (f, st2, (json.loads(body2).get('message', '') if body2 else '')[:120]))
    elif isinstance(rs, str):
        # 内容变化，带 sha 更新
        st2, body2 = api('contents/%s' % f, 'PUT', {'message': 'update %s' % f, 'content': b64, 'sha': rs})
        if st2 in (200, 201):
            updated += 1
            print('UPDATE %s' % f)
        else:
            fail += 1
            print('FAIL %s -> %s %s' % (f, st2, (json.loads(body2).get('message', '') if body2 else '')[:120]))
    else:
        # rs 为 False（远端读取失败）：保守跳过，假定服务端已是最新
        print('SKIP(远端读取失败,保守) %s' % f)
        skip += 1
print('\n完成：新增 %d / 更新 %d / 跳过 %d / 失败 %d / 共 %d' % (added, updated, skip, fail, len(to_push)))
purge_pycache()
sys.exit(1 if fail else 0)
