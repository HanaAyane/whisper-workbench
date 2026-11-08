from pathlib import Path

from PyInstaller.utils.hooks import collect_delvewheel_libs_directory, collect_dynamic_libs

root = Path(SPECPATH)
datas, av_libraries = collect_delvewheel_libs_directory("av")
analysis = Analysis(
    [str(root / "sidecar_entry.py")],
    pathex=[str(root)],
    binaries=av_libraries + collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime"),
    datas=datas,
    hiddenimports=[
        "uvicorn.lifespan.on",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.wsproto_impl",
    ],
    excludes=["pytest", "ruff", "torch", "tensorflow", "transformers"],
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="jp-sidecar", console=True, upx=False)
bundle = COLLECT(exe, analysis.binaries, analysis.datas, name="sidecar", upx=False)
