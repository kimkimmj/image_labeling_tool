# 함수 Docstring 규칙

모든 함수(메서드 포함)는 반드시 Python docstring(`""" ... """`)을 작성한다.

## 필수 작성 항목

각 함수의 docstring에는 아래 내용을 반드시 포함한다.

1. 함수의 역할(무엇을 하는지)
2. 언제 사용하는지(호출 시점/사용 맥락)
3. 필요한 경우 입력/출력 또는 예외에 대한 핵심 설명

## 예시

```python
def create_session(user_id: int) -> str:
    """사용자 세션을 생성하고 세션 ID를 반환한다.

    로그인 성공 직후, API 요청 인증에 사용할 세션을 발급할 때 사용한다.
    """
    ...
```

## FastAPI + Python을 스프링부트 스타일로 작성하는 규칙

Java(Spring Boot) 개발자 관점에서, 이 프로젝트의 FastAPI 코드는 아래 방식으로 작성한다.

1. **Controller-Service-Repository 계층 분리** (`domains/<name>/` 단위)
   - `router.py`: Controller 역할. 요청/응답, 인증, 스키마 검증만 담당
   - `services/`: 비즈니스 로직, 유스케이스 흐름, 트랜잭션 경계 담당
   - `repositories/`: DB 접근 전담
   - 라우터에서 직접 SQLAlchemy 처리 금지

2. **클래스 기반으로 작성 (함수 나열 금지)**
   - Service, Repository는 클래스로 정의한다.
   - 상태가 필요 없더라도 도메인 단위 클래스로 묶는다.
   - 단일 책임 원칙(SRP)을 지키고, 메서드 이름은 유스케이스 중심으로 작성한다.

3. **의존성 주입은 FastAPI `Depends`로 통일**
   - Spring의 생성자 주입처럼, 라우터는 `Depends`로 Service를 주입받는다.
   - Service는 필요 Repository를 생성자에서 주입받아 조합한다.
   - 전역 싱글톤/숨은 의존성(모듈 전역 객체 직접 참조) 사용을 지양한다.

4. **DTO(스키마)와 엔티티를 분리**
   - API 입출력은 Pydantic 스키마를 사용한다.
   - DB 모델(SQLAlchemy)과 API 스키마를 직접 혼용하지 않는다.
   - Controller에서는 스키마를 받고, Service에서는 도메인 의미로 처리한다.

5. **예외 처리 책임을 Service에 둔다**
   - 비즈니스 규칙 위반 예외는 Service에서 정의/발생시킨다.
   - Router는 예외를 HTTP 응답으로 변환하는 역할만 담당한다.

6. **트랜잭션 경계를 명시한다**
   - DB 쓰기 작업이 2개 이상 이어지면 Service에서 트랜잭션 경계를 명시한다.
   - Repository는 쿼리 실행에 집중하고, 유스케이스 단위 원자성은 Service가 보장한다.

7. **네이밍도 스프링 스타일로 명확하게**
   - `DatasetService`, `DatasetRepository`, `DatasetCreateRequest`, `DatasetResponse`처럼 역할이 드러나게 작성한다.
   - 메서드는 `create_dataset`, `approve_annotation`, `assign_annotator`처럼 동사 중심으로 작성한다.

## FastAPI에서의 스프링부트 스타일 예시

```python
class DatasetService:
    """데이터셋 유스케이스를 처리한다.

    Router에서 전달된 요청을 도메인 규칙에 맞게 처리하고,
    필요한 저장소 작업을 조합할 때 사용한다.
    """

    def __init__(self, repository: DatasetRepository) -> None:
        self._repository = repository

    def create_dataset(self, request: DatasetCreateRequest) -> DatasetResponse:
        """새 데이터셋을 생성한다.

        데이터셋 생성 API 호출 시점에 사용하며,
        비즈니스 검증 후 저장소에 영속화한다.
        """
        ...
```