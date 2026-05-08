# STEP 구현 플랜 저장 위치

- 단계별 구현 플랜(마크다운)은 **`.cursor/plans/`** 에 저장한다.
- 파일명·관례는 **`.cursor/step.md`** 의 「Plan 저장 경로」절을 따른다.

예: STEP 1 OAuth·세션 플랜 → [`../plans/step-01-auth-oauth-session.plan.md`](../plans/step-01-auth-oauth-session.plan.md)

---

## 규칙용 플랜 (`.cursor/rules/plan.md`)

- 진행 중인 단일 플랜을 규칙 옆에 두고 싶을 때 **`.cursor/rules/plan.md`** 에 둘 수 있다.
- 이 파일을 기준으로 작업할 때도 아래 「플랜 실행 시 질문 정리」를 적용한다.
- 이 경우 질문 요약 파일명은 플랜 파일명과 동일하게 **`docs/questions/plan.md`** 이다.

---

## 플랜 실행 시 질문 정리 (`docs/questions/`)

플랜을 만들거나 플랜대로 구현을 진행하는 동안 Cursor가 한 **심문·추가 질문·가정 확인**은, 나중에 맥락을 복기할 수 있도록 마크다운으로 남긴다.

1. **저장 위치**: `/home/corestone/sources/image_labeling_tool/docs/questions/`
2. **파일명**: 플랜 파일과 **이름을 동일하게** 한다 (확장자 `.md`).
   - 예: `.cursor/plans/step-04-upload.plan.md` → `docs/questions/step-04-upload.plan.md`
   - 예: `.cursor/rules/plan.md` → `docs/questions/plan.md`
3. **내용**: 대화에서 나온 질문을 번호· bullet 로 정리하고, 각 항목에 **최종 합의된 답(또는 사용자 답변 요약)** 을 붙인다. 모호했던 부분만이라도 남겨도 된다.
4. **시점**: 플랜을 확정했을 때 또는 해당 STEP 구현을 마무리할 때 같은 PR·같은 커밋 묶음에서 갱신하는 것을 권장한다 (플랜 대비 실제 결정이 드러나도록).

이 규칙은 플랜 저장 위치(`.cursor/plans/` 또는 `.cursor/rules/plan.md`)와 짝을 이루도록 한다.

