from enum import Enum


class FixAuthenticationMethod(str, Enum):
    PASSWORD = "password"
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA256_TIMESTAMP = "hmac_sha256_timestamp"
