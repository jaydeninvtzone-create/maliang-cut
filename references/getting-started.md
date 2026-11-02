# 命令与草稿打开

以下命令在技能目录执行，python应替换为安装依赖所用的同一解释器。素材路径由用户提供，不上传素材。计划格式见[计划合同](plan.md)。

```powershell
python scripts/maliang.py doctor
python scripts/maliang.py inspect "素材目录/原片.mp4"
python scripts/maliang.py validate "项目目录/plan.json" --media-root "素材目录"
python scripts/maliang.py build "项目目录/plan.json" --media-root "素材目录" --out "新的草稿目录"
```

草稿生成后，正常退出剪映，包括托盘。草稿根目录来自本机剪映设置或实际既有目录，须已有root_meta_info.json，不猜测并新建空索引。

```powershell
python scripts/maliang.py register-draft "新的草稿目录" --draft-root "剪映实际草稿根目录" --media-root "素材目录"
```

登记成功，再启动剪映，从首页按计划名称打开。命令只接纳本包新生成且验证通过的草稿。旧工程、加密工程、人工修改过的工程不能拿旧JSON覆盖。详见[登记合同](registration.md)。

完成原生编辑和导出后：

```powershell
python scripts/maliang.py verify "成片.mp4" --duration 120
```

此处120替换为实际计划总时长；检测容差0.15秒。verify遇到解码错误停止，技术通过仍需正常速度完整看、听。preview只是有限的无字幕、无变换主轨粗剪，不能冒充剪映导出。

修改时给时间码和目的，保留旧版，再调整新版本。手工编辑后继续在原生工程改，不重新build覆盖。封面、标题由Codex另外制作，不由build自动生成。
