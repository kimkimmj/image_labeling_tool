import base64
import hashlib
import secrets


class PkceGenerator:
    """RFC 7636 PKCE verifier/challenge 생성.

    Google·Kakao 등 기밀 클라이언트와 함께 인가 요청을 만들 때 OAuthLoginService가 사용한다.
    """

    def generate_pair(self) -> tuple[str, str]:
        """무작위 verifier와 해당 S256 challenge를 반환한다.

        로그인 URL 생성 직전에 호출하며, verifier는 HttpOnly 쿠키에 저장한다.

        Returns:
            (code_verifier, code_challenge) 문자열 쌍.
        """
        verifier = secrets.token_urlsafe(64)
        return verifier, self.challenge_from_verifier(verifier)

    def challenge_from_verifier(self, verifier: str) -> str:
        """verifier로부터 BASE64URL(SHA256(verifier)) challenge를 만든다."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
