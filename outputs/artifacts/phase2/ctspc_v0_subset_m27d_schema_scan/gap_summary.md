# Phase-2 Target Subset Gap Report

- Prompt/family candidates: `121`
- Schema-local candidates: `34`
- Schema-filtered out: `87`
- Selected cases: `30`
- Eligible for execution: `True`

## Reason Distribution

- `insufficient_local_evidence`: `34`
- `non_target_schema`: `87`

## Cases

| Case | Target Tools | Mined Recommended | Mined Candidates | Reason |
| --- | --- | --- | --- | --- |
| multi_turn_miss_param_17 | find, ls | - | - | insufficient_local_evidence |
| multi_turn_miss_param_19 | cat, cd, cp, find, grep, mv | - | - | insufficient_local_evidence |
| multi_turn_miss_param_31 | find, grep, mkdir, mv | - | - | insufficient_local_evidence |
| multi_turn_miss_param_38 | find, grep, mkdir, sort | - | - | insufficient_local_evidence |
| multi_turn_miss_param_3 | cd, cp, find | - | - | insufficient_local_evidence |
| multi_turn_miss_param_5 | cat, cd, find, mv, sort | - | - | insufficient_local_evidence |
| multi_turn_miss_param_7 | cat, cd, diff, echo, mkdir, sort | - | - | insufficient_local_evidence |
| multi_turn_miss_param_16 | cat, cp, mv, sort | - | - | insufficient_local_evidence |
| multi_turn_miss_param_22 | cat, cp, diff, mv, touch | - | - | insufficient_local_evidence |
| multi_turn_miss_param_2 | cat, cp, diff, echo, mv, touch | - | - | insufficient_local_evidence |
| multi_turn_miss_param_6 | cat, cp, mv, touch | - | - | insufficient_local_evidence |
| multi_turn_miss_param_9 | cat, cd, cp, mv, sort, touch | - | - | insufficient_local_evidence |
| multi_turn_miss_param_10 | cat, cp, diff, mkdir, mv, touch | - | - | insufficient_local_evidence |
| multi_turn_miss_param_18 | cat, cp, diff, mv, sort | - | - | insufficient_local_evidence |
| multi_turn_miss_param_21 | cat, cp, diff, mv, touch | - | - | insufficient_local_evidence |
| multi_turn_miss_param_28 | find, grep, mkdir, sort, tail | - | - | insufficient_local_evidence |
| multi_turn_miss_param_35 | cat, find, grep, mv, sort | - | - | insufficient_local_evidence |
| multi_turn_miss_param_36 | cp, grep, mv, tail, touch | - | - | insufficient_local_evidence |
| multi_turn_miss_param_40 | cp, find, grep, ls, mv, tail | - | - | insufficient_local_evidence |
| multi_turn_miss_param_43 | cp, find, grep, ls, mv, tail | - | - | insufficient_local_evidence |
| multi_turn_miss_param_45 | cat, cp, find, mkdir, mv | - | - | insufficient_local_evidence |
| multi_turn_miss_param_0 | diff, find, grep, mv, sort | - | - | insufficient_local_evidence |
| multi_turn_miss_param_4 | cd, echo, sort | - | - | insufficient_local_evidence |
| multi_turn_miss_param_8 | diff, echo, grep, sort | - | - | insufficient_local_evidence |
| multi_turn_miss_param_25 | cat, cp, find, mkdir, mv, sort | - | - | insufficient_local_evidence |
| multi_turn_miss_param_27 | cp, touch | - | - | insufficient_local_evidence |
| multi_turn_miss_param_29 | cp, find, grep, mkdir, mv | - | - | insufficient_local_evidence |
| multi_turn_miss_param_30 | cat, find, mkdir, mv | - | - | insufficient_local_evidence |
| multi_turn_miss_param_37 | cat, cd, echo, grep, tail | - | - | insufficient_local_evidence |
| multi_turn_miss_param_39 | cd, echo, mkdir, sort, tail | - | - | insufficient_local_evidence |
| multi_turn_miss_param_42 | cat, cd, echo, sort, touch | - | - | insufficient_local_evidence |
| multi_turn_miss_param_49 | cd, echo, sort, tail | - | - | insufficient_local_evidence |
| multi_turn_miss_param_86 | - | - | - | non_target_schema |
| multi_turn_miss_param_117 | - | - | - | non_target_schema |
| multi_turn_miss_param_34 | cd, cp, grep, mv, sort, tail, touch | - | - | insufficient_local_evidence |
| multi_turn_miss_param_53 | - | - | - | non_target_schema |
| multi_turn_miss_param_54 | - | - | - | non_target_schema |
| multi_turn_miss_param_73 | - | - | - | non_target_schema |
| multi_turn_miss_param_90 | - | - | - | non_target_schema |
| multi_turn_miss_param_97 | - | - | - | non_target_schema |
| multi_turn_miss_param_102 | - | - | - | non_target_schema |
| multi_turn_miss_param_104 | - | - | - | non_target_schema |
| multi_turn_miss_param_109 | - | - | - | non_target_schema |
| multi_turn_miss_param_110 | - | - | - | non_target_schema |
| multi_turn_miss_param_114 | - | - | - | non_target_schema |
| multi_turn_miss_param_125 | - | - | - | non_target_schema |
| multi_turn_miss_param_130 | - | - | - | non_target_schema |
| multi_turn_miss_param_137 | - | - | - | non_target_schema |
| multi_turn_miss_param_147 | - | - | - | non_target_schema |
| multi_turn_miss_param_156 | - | - | - | non_target_schema |
| multi_turn_miss_param_161 | - | - | - | non_target_schema |
| multi_turn_miss_param_167 | - | - | - | non_target_schema |
| multi_turn_miss_param_168 | - | - | - | non_target_schema |
| multi_turn_miss_param_169 | - | - | - | non_target_schema |
| multi_turn_miss_param_172 | - | - | - | non_target_schema |
| multi_turn_miss_param_173 | - | - | - | non_target_schema |
| multi_turn_miss_param_183 | - | - | - | non_target_schema |
| multi_turn_miss_param_185 | - | - | - | non_target_schema |
| multi_turn_miss_param_187 | - | - | - | non_target_schema |
| multi_turn_miss_param_197 | - | - | - | non_target_schema |
| multi_turn_miss_param_198 | - | - | - | non_target_schema |
| multi_turn_miss_param_199 | - | - | - | non_target_schema |
| multi_turn_miss_param_41 | cd, find, ls | - | - | insufficient_local_evidence |
| multi_turn_miss_param_56 | - | - | - | non_target_schema |
| multi_turn_miss_param_58 | - | - | - | non_target_schema |
| multi_turn_miss_param_61 | - | - | - | non_target_schema |
| multi_turn_miss_param_62 | - | - | - | non_target_schema |
| multi_turn_miss_param_63 | - | - | - | non_target_schema |
| multi_turn_miss_param_64 | - | - | - | non_target_schema |
| multi_turn_miss_param_65 | - | - | - | non_target_schema |
| multi_turn_miss_param_66 | - | - | - | non_target_schema |
| multi_turn_miss_param_67 | - | - | - | non_target_schema |
| multi_turn_miss_param_68 | - | - | - | non_target_schema |
| multi_turn_miss_param_69 | - | - | - | non_target_schema |
| multi_turn_miss_param_71 | - | - | - | non_target_schema |
| multi_turn_miss_param_72 | - | - | - | non_target_schema |
| multi_turn_miss_param_75 | - | - | - | non_target_schema |
| multi_turn_miss_param_76 | - | - | - | non_target_schema |
| multi_turn_miss_param_77 | - | - | - | non_target_schema |
| multi_turn_miss_param_81 | - | - | - | non_target_schema |
| multi_turn_miss_param_83 | - | - | - | non_target_schema |
| multi_turn_miss_param_84 | - | - | - | non_target_schema |
| multi_turn_miss_param_88 | - | - | - | non_target_schema |
| multi_turn_miss_param_89 | - | - | - | non_target_schema |
| multi_turn_miss_param_91 | - | - | - | non_target_schema |
| multi_turn_miss_param_92 | - | - | - | non_target_schema |
| multi_turn_miss_param_93 | - | - | - | non_target_schema |
| multi_turn_miss_param_94 | - | - | - | non_target_schema |
| multi_turn_miss_param_95 | - | - | - | non_target_schema |
| multi_turn_miss_param_99 | - | - | - | non_target_schema |
| multi_turn_miss_param_103 | - | - | - | non_target_schema |
| multi_turn_miss_param_106 | - | - | - | non_target_schema |
| multi_turn_miss_param_107 | - | - | - | non_target_schema |
| multi_turn_miss_param_108 | - | - | - | non_target_schema |
| multi_turn_miss_param_113 | - | - | - | non_target_schema |
| multi_turn_miss_param_121 | - | - | - | non_target_schema |
| multi_turn_miss_param_126 | - | - | - | non_target_schema |
| multi_turn_miss_param_131 | - | - | - | non_target_schema |
| multi_turn_miss_param_140 | - | - | - | non_target_schema |
| multi_turn_miss_param_141 | - | - | - | non_target_schema |
| multi_turn_miss_param_142 | - | - | - | non_target_schema |
| multi_turn_miss_param_143 | - | - | - | non_target_schema |
| multi_turn_miss_param_144 | - | - | - | non_target_schema |
| multi_turn_miss_param_148 | - | - | - | non_target_schema |
| multi_turn_miss_param_152 | - | - | - | non_target_schema |
| multi_turn_miss_param_155 | - | - | - | non_target_schema |
| multi_turn_miss_param_158 | - | - | - | non_target_schema |
| multi_turn_miss_param_159 | - | - | - | non_target_schema |
| multi_turn_miss_param_166 | - | - | - | non_target_schema |
| multi_turn_miss_param_171 | - | - | - | non_target_schema |
| multi_turn_miss_param_174 | - | - | - | non_target_schema |
| multi_turn_miss_param_177 | - | - | - | non_target_schema |
| multi_turn_miss_param_178 | - | - | - | non_target_schema |
| multi_turn_miss_param_180 | - | - | - | non_target_schema |
| multi_turn_miss_param_181 | - | - | - | non_target_schema |
| multi_turn_miss_param_182 | - | - | - | non_target_schema |
| multi_turn_miss_param_188 | - | - | - | non_target_schema |
| multi_turn_miss_param_190 | - | - | - | non_target_schema |
| multi_turn_miss_param_194 | - | - | - | non_target_schema |
| multi_turn_miss_param_195 | - | - | - | non_target_schema |
| multi_turn_miss_param_196 | - | - | - | non_target_schema |
