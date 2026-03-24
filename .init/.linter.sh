#!/bin/bash
cd /tmp/kavia/workspace/code-generation/unified-task-planner-243915-243929/fastapi_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

