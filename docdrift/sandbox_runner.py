"""Token Factory Sandboxes (ConTree) runner. UNVERIFIED: written from docs, never run.
Needs `pip install contree-sdk` and a configured client. Base image and lib upload are assumptions to test."""
from .interfaces import RunResult

class SandboxRunner:
    def __init__(self, sdk, image_tag="python:3.11", timeout=30):
        self.sdk, self.image_tag, self.timeout = sdk, image_tag, timeout

    def run(self, code, repo_dir):
        # TODO(verify): upload repo_dir/lib into the sandbox; docs show image.run(shell=..., stdin=...).wait()
        image = self.sdk.images.use(self.image_tag)
        res = image.run(shell="python3 -", stdin=code).wait()
        return RunResult(res.exit_code == 0, res.stdout or "", res.stderr or "")
