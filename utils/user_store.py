import hashlib
import json
import os
import secrets
from path_tool import get_abs_path
from logger_handler import logger

#账号文件放在 data/ 下（已被 .gitignore 忽略），避免凭据进入仓库
USERS_FILE = get_abs_path(os.path.join("data", "users.json"))
PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 6


def _load_users()->dict:
    if not os.path.exists(USERS_FILE):
        return {}

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[用户存储]读取 {USERS_FILE} 失败: {e}")
        return {}


def _save_users(users:dict):
    #先写临时文件再替换，避免写入过程中断导致账号库损坏
    tmp_path = USERS_FILE + ".tmp"
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, USERS_FILE)


def _hash_password(password:str, salt:bytes)->str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    ).hex()


def user_exists(username:str)->bool:
    return username in _load_users()


#注册成功返回 (True, "")，失败返回 (False, 失败原因)
def register_user(username:str, password:str)->tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "用户名不能为空！"
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"密码长度不能少于 {MIN_PASSWORD_LENGTH} 位！"

    users = _load_users()
    if username in users:
        return False, f"用户名 {username} 已被注册，请直接登录。"

    salt = secrets.token_bytes(SALT_BYTES)
    users[username] = {
        "salt": salt.hex(),
        "password_hash": _hash_password(password, salt),
    }
    _save_users(users)
    logger.info(f"[用户存储]新用户 {username} 注册成功")
    return True, ""


#登录校验失败返回 (False, 失败原因)
def verify_user(username:str, password:str)->tuple[bool, str]:
    username = username.strip()
    users = _load_users()
    record = users.get(username)
    if record is None:
        return False, f"用户名 {username} 尚未注册，请先注册。"

    salt = bytes.fromhex(record["salt"])
    if not secrets.compare_digest(_hash_password(password, salt), record["password_hash"]):
        return False, "用户名或密码错误！"

    logger.info(f"[用户存储]用户 {username} 登录成功")
    return True, ""
