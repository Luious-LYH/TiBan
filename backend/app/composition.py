"""FastAPI composition root for selected Stage 6 application boundaries."""

from app.adapters.practice_stage1 import Stage1PracticeWorkflowAdapter
from app.application.practice.use_cases import PracticeUseCases
from app.services.stage1_service import stage1_service


practice_use_cases = PracticeUseCases(Stage1PracticeWorkflowAdapter(stage1_service))
