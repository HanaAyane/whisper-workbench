---
name: Whisper工作台
description: 本地日语转写工作台。左栏导航，正文实底，玻璃只留在栏和浮层。
colors:
  paper: "#f4f6fb"
  paper-dark: "#1a1d27"
  ink: "#171b28"
  ink-dark: "#f3f5ff"
  muted: "#3a4358"
  muted-dark: "#c5cbe0"
  line: "#d5dbe8"
  accent: "#4d42b8"
  accent-ink: "#3c328f"
  accent-soft: "#e4e0fb"
  status: "#0e5340"
  status-dark: "#9ee4cb"
  error: "#7c2038"
  rail-solid: "#e7ebf4"
  rail-solid-dark: "#222633"
typography:
  body:
    fontFamily: "Segoe UI, Microsoft YaHei UI, Yu Gothic UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0em"
  title:
    fontFamily: "Segoe UI, Microsoft YaHei UI, Yu Gothic UI, sans-serif"
    fontSize: "18px"
    fontWeight: 680
    lineHeight: 1.3
    letterSpacing: "-0.02em"
rounded:
  sm: "8px"
  md: "10px"
  lg: "14px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "5px 12px"
    height: "32px"
  button-nav-current:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.sm}"
    padding: "5px 8px"
    height: "32px"
---

## Overview

Whisper工作台是一个 Electron 窗口里的转写工具。左栏承担导航，右边是当前页。玻璃用在左栏、顶栏和消息浮层，盖在一张黄昏窗边照片上。文稿、文件表、任务列表和设置正文是实底，方便阅读。

## Colors

浅色正文是 `{colors.paper}` 上的 `{colors.ink}`。次要文字用 `{colors.muted}`。主操作和当前导航用 `{colors.accent}`。成功状态用 `{colors.status}`，错误用 `{colors.error}`。深色主题换成 `{colors.paper-dark}` 和 `{colors.ink-dark}`。

玻璃栏的实色退路是 `{colors.rail-solid}`。`prefers-reduced-transparency: reduce` 时栏和顶栏改用这层实色，并关掉 backdrop-filter。

## Typography

界面用系统无衬线，正文 13px。页标题 18px，只出现在术语表和设置。时间码用等宽数字。不使用展示字体，也不加大标题。

## Layout

窗口是两列，中间没有照片缝。左栏宽度只包住产品名和「图标 + 文字」，设置钉在底部。右边顶栏紧贴窗口上沿。工作区从栏边铺到窗口边缘，不再把实底页面做成漂在照片上的卡片。新建页上排是录音和拖放，中间是文件表，底排是模型、模式、词表和提交。工作台左列是任务，右列是文稿，导出条贴在右列底部。窄于 980px 时设置和术语表改为单列。

## Elevation & Depth

实底页面贴着栏和窗口，不再用阴影把自己托成卡片。玻璃的边缘折射来自 Glasswork 的 `backdrop-filter`，末尾是 `var(--glass-lens,)`。照片只从左栏和顶栏透出来。

## Shapes

控件圆角 8px，文件表和分段 10px。页面实底贴边，不用圆角。左栏和顶栏也贴边。

## Components

主导航是整行按钮，当前项用浅紫底和 `{colors.accent-ink}`。主按钮是紫底白字。文件表列出名称、采样、体积和状态。导出条提供 SRT、VTT、LRC、TXT。消息浮层用玻璃，正文里的缺模型提示用实底。

## Do's and Don'ts

### Do

- 把新的常驻导航放进左栏，设置留在栏底。
- 玻璃只加在盖住照片的栏、顶栏、弹窗和浮层上。
- 保持现有中文文案和现有任务、导出、术语表接线。

### Don't

- 不要在文稿编辑区铺玻璃。
- 不要恢复波浪壁纸或大标题。
- 不要在没有文件头数据时编造采样率。
