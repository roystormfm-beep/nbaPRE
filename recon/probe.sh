#!/bin/bash
# Prova di raggiungibilità delle fonti dal workspace cloud
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'
probe() {
  local name="$1" url="$2"; shift 2
  local out
  out=$(curl -s -o /tmp/probe_body -w '%{http_code} %{size_download} %{time_total}' --max-time 20 -A "$UA" "$@" "$url" 2>&1)
  local rc=$?
  printf '%-34s rc=%-3s %s\n' "$name" "$rc" "$out"
  head -c 160 /tmp/probe_body | tr '\n' ' ' | sed 's/^/    /'; echo
}
probe "stats.nba.com scoreboard"   "https://stats.nba.com/stats/scoreboardv2?GameDate=2026-11-20&LeagueID=00&DayOffset=0" -H 'Referer: https://www.nba.com/' -H 'Origin: https://www.nba.com' -H 'x-nba-stats-origin: stats' -H 'x-nba-stats-token: true'
probe "cdn.nba.com schedule"       "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
probe "cdn.nba.com todaysScoreboard" "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
probe "api.pbpstats.com"           "https://api.pbpstats.com/get-games/nba?Season=2025-26&SeasonType=Regular%2BSeason"
probe "basketball-reference"       "https://www.basketball-reference.com/leagues/NBA_2027_games-november.html"
probe "official.nba.com injury"    "https://official.nba.com/nba-injury-report-2026-27-season/"
probe "ak-static injury pdf"       "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-22_06PM.pdf"
probe "official.nba.com referees"  "https://official.nba.com/referee-assignments/"
probe "espn site api"              "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
probe "the-odds-api"               "https://api.the-odds-api.com/v4/sports"
probe "sportsbookreviewsonline"    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba/nbaoddsarchives.htm"
probe "kaggle api"                 "https://www.kaggle.com/api/v1/datasets/list?search=nba"
probe "github api"                 "https://api.github.com/repos/shufinskiy/nba_data"
probe "raw.githubusercontent"      "https://raw.githubusercontent.com/shufinskiy/nba_data/main/README.md"
probe "github releases (objects)"  "https://github.com/shufinskiy/nba_data/releases"
probe "pypi"                       "https://pypi.org/simple/nba-api/"
probe "huggingface"                "https://huggingface.co/api/datasets?search=nba"
