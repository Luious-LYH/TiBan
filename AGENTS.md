# AGENTS.md

## Project Identity

Project: **内镜智训Agent：面向消化道内镜医师培训的智能辅导平台**

This repository is for medical education, intelligent tutoring, explainable error feedback, and doctor-review-before-use assistance. It must never present itself as an autonomous clinical diagnosis system.

## Current Scope

- Build a runnable React + FastAPI demo platform.
- Keep model evaluation as mock/reserved only.
- Use mock or synthetic data only.
- Preserve safety notices and auditability across all medical outputs.

## Safety Rules

- Do not write real server IPs, passwords, API keys, webhooks, tokens, patient names, ID numbers, visit numbers, or any identifiable patient data.
- Do not output final clinical diagnoses or treatment instructions.
- Report drafts and patient cards must set `doctor_review_required=true`.
- Medical outputs must include: `仅供教学训练或医生审核前辅助，不作为独立诊断依据。`
- The model hub must clearly state that capability scores are mock/reserved.

## Engineering Rules

- Keep frontend and backend independently runnable.
- Prefer small service modules over large single files.
- Keep API fields aligned with `03_系统需求规格与接口数据字典.md`.
- Frontend API calls must include backend fallback behavior.
- Backend must start with `uvicorn app.main:app --reload` from the `backend` directory.

