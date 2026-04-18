Problem: Jobstart auf frischem Hub kann mit 500 scheitern, weil der JobStore in ein nicht existierendes State-Unterverzeichnis schreibt.
Ursache: Parent-Verzeichnis für `jobs.tmp` wird vor `write_text()` nicht garantiert angelegt.
Fix: JobStore legt das benötigte Parent-Verzeichnis vor dem Schreiben robust an.
Test: Neuer Test `test_create_job_fresh_hub_no_state_dir` deckt frischen Hub ohne vorhandenes `.rlens-service/` ab.
