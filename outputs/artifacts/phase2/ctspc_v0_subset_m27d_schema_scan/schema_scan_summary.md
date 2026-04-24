# Phase-2 Schema Scan Summary

- Total cases: `121`
- Cases with TARGET_ACTION_TOOLS: `34`
- ACTIONABLE_NO_TOOL_DECISION overlap: `0`
- POST_TOOL_PROSE_SUMMARY overlap: `0`

## Target Tool Distribution

- `cat`: `17`
- `cd`: `12`
- `cp`: `18`
- `diff`: `8`
- `echo`: `8`
- `find`: `16`
- `grep`: `13`
- `ls`: `4`
- `mkdir`: `10`
- `mv`: `21`
- `sort`: `16`
- `tail`: `8`
- `touch`: `10`

## Schema Sources

- `prompt_path`: `121`

## Cases

| Case | Schema Source | Target Tools | Failure Labels | Keyword Score |
| --- | --- | --- | --- | ---: |
| multi_turn_miss_param_17 | prompt_path | find, ls | - | 5 |
| multi_turn_miss_param_19 | prompt_path | cat, cd, cp, find, grep, mv | - | 5 |
| multi_turn_miss_param_31 | prompt_path | find, grep, mkdir, mv | - | 5 |
| multi_turn_miss_param_38 | prompt_path | find, grep, mkdir, sort | - | 5 |
| multi_turn_miss_param_3 | prompt_path | cd, cp, find | - | 4 |
| multi_turn_miss_param_5 | prompt_path | cat, cd, find, mv, sort | - | 4 |
| multi_turn_miss_param_7 | prompt_path | cat, cd, diff, echo, mkdir, sort | - | 4 |
| multi_turn_miss_param_16 | prompt_path | cat, cp, mv, sort | - | 4 |
| multi_turn_miss_param_22 | prompt_path | cat, cp, diff, mv, touch | - | 4 |
| multi_turn_miss_param_2 | prompt_path | cat, cp, diff, echo, mv, touch | - | 3 |
| multi_turn_miss_param_6 | prompt_path | cat, cp, mv, touch | - | 3 |
| multi_turn_miss_param_9 | prompt_path | cat, cd, cp, mv, sort, touch | - | 3 |
| multi_turn_miss_param_10 | prompt_path | cat, cp, diff, mkdir, mv, touch | - | 3 |
| multi_turn_miss_param_18 | prompt_path | cat, cp, diff, mv, sort | - | 3 |
| multi_turn_miss_param_21 | prompt_path | cat, cp, diff, mv, touch | - | 3 |
| multi_turn_miss_param_28 | prompt_path | find, grep, mkdir, sort, tail | - | 3 |
| multi_turn_miss_param_35 | prompt_path | cat, find, grep, mv, sort | - | 3 |
| multi_turn_miss_param_36 | prompt_path | cp, grep, mv, tail, touch | - | 3 |
| multi_turn_miss_param_40 | prompt_path | cp, find, grep, ls, mv, tail | - | 3 |
| multi_turn_miss_param_43 | prompt_path | cp, find, grep, ls, mv, tail | - | 3 |
| multi_turn_miss_param_45 | prompt_path | cat, cp, find, mkdir, mv | - | 3 |
| multi_turn_miss_param_0 | prompt_path | diff, find, grep, mv, sort | - | 2 |
| multi_turn_miss_param_4 | prompt_path | cd, echo, sort | - | 2 |
| multi_turn_miss_param_8 | prompt_path | diff, echo, grep, sort | - | 2 |
| multi_turn_miss_param_25 | prompt_path | cat, cp, find, mkdir, mv, sort | - | 2 |
| multi_turn_miss_param_27 | prompt_path | cp, touch | - | 2 |
| multi_turn_miss_param_29 | prompt_path | cp, find, grep, mkdir, mv | - | 2 |
| multi_turn_miss_param_30 | prompt_path | cat, find, mkdir, mv | - | 2 |
| multi_turn_miss_param_37 | prompt_path | cat, cd, echo, grep, tail | - | 2 |
| multi_turn_miss_param_39 | prompt_path | cd, echo, mkdir, sort, tail | - | 2 |
| multi_turn_miss_param_42 | prompt_path | cat, cd, echo, sort, touch | - | 2 |
| multi_turn_miss_param_49 | prompt_path | cd, echo, sort, tail | - | 2 |
| multi_turn_miss_param_86 | prompt_path | - | - | 2 |
| multi_turn_miss_param_117 | prompt_path | - | - | 2 |
| multi_turn_miss_param_34 | prompt_path | cd, cp, grep, mv, sort, tail, touch | - | 1 |
| multi_turn_miss_param_53 | prompt_path | - | - | 1 |
| multi_turn_miss_param_54 | prompt_path | - | - | 1 |
| multi_turn_miss_param_73 | prompt_path | - | - | 1 |
| multi_turn_miss_param_90 | prompt_path | - | - | 1 |
| multi_turn_miss_param_97 | prompt_path | - | - | 1 |
| multi_turn_miss_param_102 | prompt_path | - | - | 1 |
| multi_turn_miss_param_104 | prompt_path | - | - | 1 |
| multi_turn_miss_param_109 | prompt_path | - | - | 1 |
| multi_turn_miss_param_110 | prompt_path | - | - | 1 |
| multi_turn_miss_param_114 | prompt_path | - | - | 1 |
| multi_turn_miss_param_125 | prompt_path | - | - | 1 |
| multi_turn_miss_param_130 | prompt_path | - | - | 1 |
| multi_turn_miss_param_137 | prompt_path | - | - | 1 |
| multi_turn_miss_param_147 | prompt_path | - | - | 1 |
| multi_turn_miss_param_156 | prompt_path | - | - | 1 |
| multi_turn_miss_param_161 | prompt_path | - | - | 1 |
| multi_turn_miss_param_167 | prompt_path | - | - | 1 |
| multi_turn_miss_param_168 | prompt_path | - | - | 1 |
| multi_turn_miss_param_169 | prompt_path | - | - | 1 |
| multi_turn_miss_param_172 | prompt_path | - | - | 1 |
| multi_turn_miss_param_173 | prompt_path | - | - | 1 |
| multi_turn_miss_param_183 | prompt_path | - | - | 1 |
| multi_turn_miss_param_185 | prompt_path | - | - | 1 |
| multi_turn_miss_param_187 | prompt_path | - | - | 1 |
| multi_turn_miss_param_197 | prompt_path | - | - | 1 |
| multi_turn_miss_param_198 | prompt_path | - | - | 1 |
| multi_turn_miss_param_199 | prompt_path | - | - | 1 |
| multi_turn_miss_param_41 | prompt_path | cd, find, ls | - | 0 |
| multi_turn_miss_param_56 | prompt_path | - | - | 0 |
| multi_turn_miss_param_58 | prompt_path | - | - | 0 |
| multi_turn_miss_param_61 | prompt_path | - | - | 0 |
| multi_turn_miss_param_62 | prompt_path | - | - | 0 |
| multi_turn_miss_param_63 | prompt_path | - | - | 0 |
| multi_turn_miss_param_64 | prompt_path | - | - | 0 |
| multi_turn_miss_param_65 | prompt_path | - | - | 0 |
| multi_turn_miss_param_66 | prompt_path | - | - | 0 |
| multi_turn_miss_param_67 | prompt_path | - | - | 0 |
| multi_turn_miss_param_68 | prompt_path | - | - | 0 |
| multi_turn_miss_param_69 | prompt_path | - | - | 0 |
| multi_turn_miss_param_71 | prompt_path | - | - | 0 |
| multi_turn_miss_param_72 | prompt_path | - | - | 0 |
| multi_turn_miss_param_75 | prompt_path | - | - | 0 |
| multi_turn_miss_param_76 | prompt_path | - | - | 0 |
| multi_turn_miss_param_77 | prompt_path | - | - | 0 |
| multi_turn_miss_param_81 | prompt_path | - | - | 0 |
| multi_turn_miss_param_83 | prompt_path | - | - | 0 |
| multi_turn_miss_param_84 | prompt_path | - | - | 0 |
| multi_turn_miss_param_88 | prompt_path | - | - | 0 |
| multi_turn_miss_param_89 | prompt_path | - | - | 0 |
| multi_turn_miss_param_91 | prompt_path | - | - | 0 |
| multi_turn_miss_param_92 | prompt_path | - | - | 0 |
| multi_turn_miss_param_93 | prompt_path | - | - | 0 |
| multi_turn_miss_param_94 | prompt_path | - | - | 0 |
| multi_turn_miss_param_95 | prompt_path | - | - | 0 |
| multi_turn_miss_param_99 | prompt_path | - | - | 0 |
| multi_turn_miss_param_103 | prompt_path | - | - | 0 |
| multi_turn_miss_param_106 | prompt_path | - | - | 0 |
| multi_turn_miss_param_107 | prompt_path | - | - | 0 |
| multi_turn_miss_param_108 | prompt_path | - | - | 0 |
| multi_turn_miss_param_113 | prompt_path | - | - | 0 |
| multi_turn_miss_param_121 | prompt_path | - | - | 0 |
| multi_turn_miss_param_126 | prompt_path | - | - | 0 |
| multi_turn_miss_param_131 | prompt_path | - | - | 0 |
| multi_turn_miss_param_140 | prompt_path | - | - | 0 |
| multi_turn_miss_param_141 | prompt_path | - | - | 0 |
| multi_turn_miss_param_142 | prompt_path | - | - | 0 |
| multi_turn_miss_param_143 | prompt_path | - | - | 0 |
| multi_turn_miss_param_144 | prompt_path | - | - | 0 |
| multi_turn_miss_param_148 | prompt_path | - | - | 0 |
| multi_turn_miss_param_152 | prompt_path | - | - | 0 |
| multi_turn_miss_param_155 | prompt_path | - | - | 0 |
| multi_turn_miss_param_158 | prompt_path | - | - | 0 |
| multi_turn_miss_param_159 | prompt_path | - | - | 0 |
| multi_turn_miss_param_166 | prompt_path | - | - | 0 |
| multi_turn_miss_param_171 | prompt_path | - | - | 0 |
| multi_turn_miss_param_174 | prompt_path | - | - | 0 |
| multi_turn_miss_param_177 | prompt_path | - | - | 0 |
| multi_turn_miss_param_178 | prompt_path | - | - | 0 |
| multi_turn_miss_param_180 | prompt_path | - | - | 0 |
| multi_turn_miss_param_181 | prompt_path | - | - | 0 |
| multi_turn_miss_param_182 | prompt_path | - | - | 0 |
| multi_turn_miss_param_188 | prompt_path | - | - | 0 |
| multi_turn_miss_param_190 | prompt_path | - | - | 0 |
| multi_turn_miss_param_194 | prompt_path | - | - | 0 |
| multi_turn_miss_param_195 | prompt_path | - | - | 0 |
| multi_turn_miss_param_196 | prompt_path | - | - | 0 |
