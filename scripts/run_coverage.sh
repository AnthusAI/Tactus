#!/usr/bin/env bash
set -euo pipefail

coverage erase

coverage run --parallel-mode -m pytest
after_pytest=$?

coverage run --parallel-mode -m behave

coverage combine
coverage report
coverage html

exit ${after_pytest}
