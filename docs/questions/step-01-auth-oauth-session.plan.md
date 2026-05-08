# STEP 1 (plan1) 질문·합의 정리

**연결 플랜**: [`.cursor/plans/step-01-auth-oauth-session.plan.md`](../../.cursor/plans/step-01-auth-oauth-session.plan.md)

이 문서는 위 플랜 구현 과정에서 나온 **심문·가정·범위**를 플랜과 1:1로 매핑해 두었다. 플랜 본문의 제품 정책과 충돌 시 **코드·이 문서 기준을 우선**하고, 플랜 YAML의 오래된 TODO 상태는 참고만 한다.

---

## 1. 가입·로그인·계정 모델

| 주제 | 질문/이슈 | 최종 합의 |
|------|-----------|-----------|
| 가입 경로 | 별도 회원가입 폼이 있는가? | 없음. **첫 OAuth 성공 = `users` 행 생성** (동일 `(provider, provider_subject)`는 동일 user). |
| 계정 병합 | 이메일이 같으면 IdP 간 자동 병합? | **아니오.** 제공자가 다르면 항상 **별도 user**. |
| 이메일 | 없으면? | 가입·세션 발급 **거절**, 명확한 에러(각 IdP 스코프·앱 설정 중요, 특히 Kakao). |
| 이메일 충돌 | 신규 OAuth 시 해당 이메일이 이미 다른 user에 존재? | **HTTP 409**. 다른 로그인 수단으로 이미 등록됨을 안내. |
| IdP 토큰 저장 | 액세스/리프레시 토큰 DB 저장? | **저장하지 않음.** API 인증은 **Redis 세션 + 세션 ID HttpOnly 쿠키**만 사용. |

---

## 2. OAuth 플로우·보안

| 주제 | 질문/이슈 | 최종 합의 |
|------|-----------|-----------|
| 콜백 위치 | SPA 직접 vs 백엔드 콜백 | **백엔드 콜백** + **PKCE**(Google/Kakao). Naver는 verifier 빈 문자열 처리. |
| PKCE verifier 보관 | 어디에 두나? | 짧은 TTL **HttpOnly 쿠키** (`state` 동일). 성공 후 플로우 쿠키 제거. |
| 세션 | 성공 후? | Redis에 세션 레코드(`user_id` 등), 브라우저에는 **무작위 세션 ID**만 HttpOnly 쿠키, TTL 정책은 설정값과 일치. |
| 로그아웃 | 무엇을 해야 하나? | **Redis 세션 키 삭제** + **세션 쿠키 만료(Set-Cookie)**. |
| CSRF | 쿠키 기반 요청 | 비안전 메서드 등에 **Origin/Referer 허용 목록** 검증. **OAuth 콜백 GET** 등은 예외 경로로 제외 (예: `/api/auth/oauth/` 접두). |

---

## 3. 프론트·출처

| 주제 | 질문/이슈 | 최종 합의 |
|------|-----------|-----------|
| 브라우저 출처 | 개발 시 API 호출 방식 | **동일 출처** 전제 — Vite 등으로 **`/api` → 백엔드 프록시**. `credentials: 'include'`로 세션 쿠키 전달. |
| OAuth 시작 | SPA에서 어떻게? | **전체 페이지 이동**으로 `/api/auth/oauth/{provider}/login` 진입 (프록시 통해 동일 호스트). |
| 로그인 UI | 미인증 시 | **`/me` 등 보호 화면 접근 시 로그인 페이지로 유도**, 소셜 버튼으로 위 URL 호출. |

---

## 4. DB·마이그레이션

| 주제 | 질문/이슈 | 최종 합의 |
|------|-----------|-----------|
| `users` 비밀번호 | OAuth만 쓰는 사용자 | **`password_hash`(또는 동등 컬럼) NULL 허용** — Alembic으로 반영. |
| OAuth 매핑 테이블 | 스키마 | **`oauth_identities`**: `UNIQUE(provider, provider_subject)`, `user_id` FK 등 — 플랜·`db_table.sql` 정렬. |
| 변경 관리 | DDL만 수정? | **Alembic revision**으로 버전 관리 (워크스페이스 규칙). |

---

## 5. 코드 배치 (대화·리팩터링 결과)

| 주제 | 질문/이슈 | 최종 합의 |
|------|-----------|-----------|
| 패키지 구조 | `app/api/` vs 도메인 | STEP 1 구현은 **`backend/app/domains/oAuth/`** 에 OAuth·세션·`/me`·로그아웃·관련 deps·서비스·리포지토리·쿠키 작성기를 모음. **`app/router.py`** 에서 도메인 라우터를 묶어 `main.py`가 `/api`로 마운트. |
| 중복 DI | 세션 스토어 등 이중 정의 | **`domains/oAuth/deps.py` 한 곳**으로 통합. |

---

## 6. STEP 1 범위에서 **제외**한 것 (플랜 YAML와의 차이)

플랜 파일 상단 TODO에 `projects-step1` 등이 있었으나, **STEP 1 완료 시점 합의로 프로젝트는 범위 밖**으로 정리했다.

- **`GET/POST /projects` API**, `domains/project/**`, SQLAlchemy의 **`Project` / `ProjectUser` 모델**은 제거됨.
- DB 참고용 DDL(`db_table.sql` 등)의 `projects`·`project_users` 테이블 정의는 **향후 스텝용**으로 문서·스키마에 남을 수 있음 — 앱 코드는 STEP 1에서 참조하지 않음.

---

## 7. API 경로 요약 (실제 마운트: `/api` 프리픽스)

| 용도 | 메서드·경로 |
|------|-------------|
| 로그인 시작 | `GET /api/auth/oauth/{google\|naver\|kakao}/login` |
| 콜백 | `GET /api/auth/oauth/{provider}/callback` |
| 현재 사용자 | `GET /api/me` |
| 로그아웃 | `POST /api/auth/logout` |

리다이렉트 URI·성공 후 프론트 URL은 **`backend/app/core/config.py`** 및 배포 환경 변수와 일치시킨다.

---

## 8. 플랜 완료 체크리스트 (요약)

- [x] Alembic: `users` 비밀번호 NULL 허용, `oauth_identities` 및 제약
- [x] Google/Naver/Kakao: 인가 URL·토큰 교환·프로필·이메일 검증·409 충돌
- [x] Redis 세션 + 세션 HttpOnly 쿠키 + 로그아웃 시 삭제
- [x] CSRF 완화 미들웨어 + OAuth 콜백 예외
- [x] 프론트: 동일 출처 프록시 + 로그인 화면 + 보호 라우트
- [x] 프로젝트 API/모델은 STEP 1 범위에서 **제거·미구현**으로 정리
