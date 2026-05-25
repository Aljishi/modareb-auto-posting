name: Rased AI — راصد

on:
  workflow_dispatch:
  push:
    branches: [main]
  schedule:
    - cron: "10 6 * * 0-4"     # 9:10 ص KSA — إشارة ذهبية (1)
    - cron: "55 6 * * 0-4"     # 9:55 ص KSA — إشارة ذهبية (2)
    - cron: "*/5 7-12 * * 0-4" # كل 5 دقائق 10ص–3م KSA — إشارة يومية
    - cron: "0 12 * * 0-4"     # 3:00م KSA — track-results
    - cron: "30 12 * * 4"      # 3:30م خميس — تقرير أسبوعي


jobs:

# ══════════════════════════════════════════════════════════════
# JOB 1: الإشارة الذهبية (9:10 و9:55 — قبل افتتاح السوق)
# مسار مستقل — historical_analyzer فقط — بدون fetch_api_data
# ══════════════════════════════════════════════════════════════
  golden-signal:
    runs-on: ubuntu-latest
    if: >
      github.event_name == 'schedule' &&
      (github.event.schedule == '10 6 * * 0-4' ||
       github.event.schedule == '55 6 * * 0-4')

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Requirements
        run: pip install -r requirements.txt
        continue-on-error: true

      - name: Golden Signal Analysis
        env:
          API_KEY:           ${{ secrets.API_KEY }}
          API_URL:           ${{ secrets.API_URL }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python scripts/historical_analyzer.py

      - name: Check Golden Signal Quality
        id: golden_check
        run: python scripts/should_post.py
        continue-on-error: true

      - name: Generate Golden Image
        if: steps.golden_check.outcome == 'success'
        run: python scripts/generate_golden_post.py
        continue-on-error: true

      - name: Log Golden Signal
        if: steps.golden_check.outcome == 'success'
        run: python scripts/log_signal.py
        continue-on-error: true

      - name: Upload output.png
        if: steps.golden_check.outcome == 'success'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python scripts/upload_output.py
        continue-on-error: true

      - name: Post Golden to Telegram
        if: steps.golden_check.outcome == 'success'
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID:   ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python scripts/post_to_telegram.py
        continue-on-error: true

      - name: Post Golden to Facebook
        if: steps.golden_check.outcome == 'success'
        env:
          FB_PAGE_ID:    ${{ secrets.FB_PAGE_ID }}
          FB_PAGE_TOKEN: ${{ secrets.FB_PAGE_TOKEN }}
          IMAGE_URL: https://raw.githubusercontent.com/${{ github.repository }}/main/output.png
        run: python scripts/post_to_facebook.py
        continue-on-error: true

      - name: Post Golden to Instagram
        if: steps.golden_check.outcome == 'success'
        env:
          FB_PAGE_ID:    ${{ secrets.FB_PAGE_ID }}
          FB_PAGE_TOKEN: ${{ secrets.FB_PAGE_TOKEN }}
          IMAGE_URL: https://raw.githubusercontent.com/${{ github.repository }}/main/output.png
        run: python scripts/post_to_instagram.py
        continue-on-error: true

      - name: Commit Golden Signal
        if: steps.golden_check.outcome == 'success'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/signals_log.csv data/golden_signal.json data/daily.json || true
          git diff --cached --quiet || git commit -m "⭐ إشارة ذهبية"
          git push || true
        continue-on-error: true


# ══════════════════════════════════════════════════════════════
# JOB 2: الإشارة اليومية (كل 5 دقائق 10ص–3م)
# مسار كامل: market_intelligence → fetch → quality → نشر
# ══════════════════════════════════════════════════════════════
  auto-post:
    runs-on: ubuntu-latest
    if: >
      (github.event_name == 'workflow_dispatch') ||
      (github.event_name == 'push') ||
      (github.event_name == 'schedule' &&
       github.event.schedule == '*/5 7-12 * * 0-4')

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Requirements
        run: pip install -r requirements.txt
        continue-on-error: true

      - name: Fetch & Analyze Market Data
        env:
          API_KEY:           ${{ secrets.API_KEY }}
          API_URL:           ${{ secrets.API_URL }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python scripts/fetch_api_data.py

      - name: Check Signal Quality
        id: quality_check
        run: python scripts/should_post.py
        continue-on-error: true

      - name: Generate Post Image
        if: steps.quality_check.outcome == 'success'
        run: python scripts/generate_post.py
        continue-on-error: true

      - name: Log Signal
        if: steps.quality_check.outcome == 'success'
        run: python scripts/log_signal.py
        continue-on-error: true

      - name: Upload output.png
        if: steps.quality_check.outcome == 'success'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python scripts/upload_output.py
        continue-on-error: true

      - name: Post to Telegram
        if: steps.quality_check.outcome == 'success'
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID:   ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python scripts/post_to_telegram.py
        continue-on-error: true

      - name: Post to Facebook
        if: steps.quality_check.outcome == 'success'
        env:
          FB_PAGE_ID:    ${{ secrets.FB_PAGE_ID }}
          FB_PAGE_TOKEN: ${{ secrets.FB_PAGE_TOKEN }}
          IMAGE_URL: https://raw.githubusercontent.com/${{ github.repository }}/main/output.png
        run: python scripts/post_to_facebook.py
        continue-on-error: true

      - name: Post to Instagram
        if: steps.quality_check.outcome == 'success'
        env:
          FB_PAGE_ID:    ${{ secrets.FB_PAGE_ID }}
          FB_PAGE_TOKEN: ${{ secrets.FB_PAGE_TOKEN }}
          IMAGE_URL: https://raw.githubusercontent.com/${{ github.repository }}/main/output.png
        run: python scripts/post_to_instagram.py
        continue-on-error: true

      - name: Commit Signal Log
        if: steps.quality_check.outcome == 'success'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/signals_log.csv data/daily.json data/market_intel.json || true
          git diff --cached --quiet || git commit -m "📊 إشارة يومية"
          git push || true
        continue-on-error: true


# ══════════════════════════════════════════════════════════════
# JOB 3: تقرير أسبوعي (خميس 3:30م)
# ══════════════════════════════════════════════════════════════
  weekly-report:
    runs-on: ubuntu-latest
    if: >
      github.event_name == 'schedule' &&
      github.event.schedule == '30 12 * * 4'

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Requirements
        run: pip install -r requirements.txt
        continue-on-error: true

      - name: Update Fundamentals
        env:
          API_KEY: ${{ secrets.API_KEY }}
          API_URL: ${{ secrets.API_URL }}
        run: python scripts/fundamentals_fetcher.py
        continue-on-error: true

      - name: Train ML Model
        env:
          API_KEY: ${{ secrets.API_KEY }}
          API_URL: ${{ secrets.API_URL }}
        run: python scripts/ml_trainer.py
        continue-on-error: true

      - name: Run Backtesting
        env:
          API_KEY: ${{ secrets.API_KEY }}
          API_URL: ${{ secrets.API_URL }}
        run: python scripts/backtester.py
        continue-on-error: true

      - name: Generate Weekly Report
        run: |
          python scripts/weekly_report.py
          python scripts/generate_report_image.py
        continue-on-error: true

      - name: Send Report to Telegram
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID:   ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python scripts/post_dashboard_to_telegram.py
        continue-on-error: true

      - name: Commit Weekly Data
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/backtest_results.json data/ml_model.json data/training_data.json data/fundamentals.json || true
          git diff --cached --quiet || git commit -m "📈 تقرير أسبوعي + ML + أساسيات"
          git push || true
        continue-on-error: true


# ══════════════════════════════════════════════════════════════
# JOB 4: متابعة نتائج الإشارات (3م يومياً)
# ══════════════════════════════════════════════════════════════
  track-results:
    runs-on: ubuntu-latest
    if: >
      github.event_name == 'schedule' &&
      github.event.schedule == '0 12 * * 0-4'

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Requirements
        run: pip install -r requirements.txt
        continue-on-error: true

      - name: Track Signal Results
        env:
          API_KEY: ${{ secrets.API_KEY }}
          API_URL: ${{ secrets.API_URL }}
        run: python scripts/track_results.py
        continue-on-error: true

      - name: Commit Results
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/signals_log.csv || true
          git diff --cached --quiet || git commit -m "📈 تحديث النتائج"
          git push || true
        continue-on-error: true
