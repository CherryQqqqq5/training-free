# M2.8-pre Literal Disambiguation Report

- Scanner missed count: `0`
- Disambiguated current-context candidates: `17`
- Source-result-only diagnostics: `8`

| Case | Tool | Arg | Selected | Cue | Rejected | Retain prior candidate |
| --- | --- | --- | --- | --- | --- | ---: |
| `multi_turn_long_context_4` | `sort` | `file_name` | `None` | `None` | `source_result_only` | `False` |
| `multi_turn_long_context_8` | `grep` | `file_name` | `experiment_log.txt` | `file_name_exact_prompt_literal` | `None` | `True` |
| `multi_turn_long_context_25` | `cat` | `file_name` | `summary.txt` | `file_name_exact_prompt_literal` | `None` | `True` |
| `multi_turn_long_context_26` | `cd` | `folder` | `None` | `None` | `source_result_only` | `False` |
| `multi_turn_long_context_24` | `diff` | `file_name1` | `None` | `None` | `source_result_only` | `False` |
| `multi_turn_miss_func_19` | `find` | `path` | `.` | `directory_cue_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_5` | `find` | `path` | `None` | `None` | `source_result_only` | `False` |
| `multi_turn_miss_func_7` | `cd` | `folder` | `academic_venture` | `directory_cue_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_16` | `mv` | `source` | `research_notes.txt` | `source_file_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_2` | `touch` | `file_name` | `TeamNotes.txt` | `file_name_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_6` | `touch` | `file_name` | `Annual_Report_2023.docx` | `file_name_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_9` | `cd` | `folder` | `Documentation` | `directory_cue_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_10` | `mkdir` | `dir_name` | `Projects` | `directory_cue_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_18` | `cat` | `file_name` | `MonthlySummary.docx` | `file_name_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_21` | `cat` | `file_name` | `ProjectOverview.txt` | `file_name_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_28` | `find` | `name` | `analysis` | `exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_0` | `mv` | `source` | `final_report.pdf` | `source_file_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_1` | `ls` | `a` | `None` | `None` | `source_result_only` | `False` |
| `multi_turn_miss_func_4` | `sort` | `file_name` | `None` | `None` | `source_result_only` | `False` |
| `multi_turn_miss_func_8` | `grep` | `file_name` | `experiment_log.txt` | `file_name_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_12` | `touch` | `file_name` | `summary.txt` | `file_name_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_25` | `cat` | `file_name` | `summary.txt` | `file_name_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_26` | `cd` | `folder` | `None` | `None` | `source_result_only` | `False` |
| `multi_turn_miss_func_15` | `touch` | `file_name` | `DataSet1.csv` | `file_name_exact_prompt_literal` | `None` | `True` |
| `multi_turn_miss_func_24` | `diff` | `file_name1` | `None` | `None` | `source_result_only` | `False` |
