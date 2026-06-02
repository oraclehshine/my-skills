# my-skills

这个目录用于存放我日常使用和维护的 Codex/AI skills。

## 目录用途

- `video-summarizer-politics/`：面向公考政治理论学习的视频整理 skill，用于把课程视频、时政解读、政治理论讲解等内容整理成学习笔记。

## 使用方式

每个 skill 建议保持独立目录，并至少包含一个 `SKILL.md` 文件。需要启用某个 skill 时，可以将对应目录复制到本机 Codex skills 目录：

```powershell
Copy-Item "E:\class\skills\<skill-name>" "$env:USERPROFILE\.codex\skills\<skill-name>" -Recurse -Force
```

复制后重启 Codex，新的 skill 才会被加载。

## 管理建议

- skill 名称尽量使用英文小写和连字符，便于跨平台管理。
- `SKILL.md` 里只保留必要说明，较长模板或参考资料可以放在 `references/`。
- 更新 skill 后，建议同步记录用途变化，避免多个版本混在一起。
