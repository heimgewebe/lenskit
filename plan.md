User feedback: The PR is conceptually perfect now and ready to merge. I can add one optional tiny polish test to check for problematic filenames that contain what used to be delimiters (e.g. `|`) to prove that JSON serialization fixes the delimiter collision issue.
Then I will submit it.

I will add one additional test to `merger/lenskit/tests/test_atlas_heuristic_subtree.py`.
