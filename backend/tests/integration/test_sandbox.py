import pytest

from app.sandbox.runner import DockerSandbox, TestCase
from app.services import question_bank as qb
from tests.conftest import requires_docker

pytestmark = [pytest.mark.docker, requires_docker]

DOUBLE = {
    "python": "n = int(input())\nprint(n * 2)\n",
    "cpp": "#include <iostream>\nint main(){long long n; std::cin>>n; std::cout<<n*2<<\"\\n\";}\n",
    "java": "import java.util.*;\npublic class Main{public static void main(String[] a){"
            "Scanner s=new Scanner(System.in);long n=s.nextLong();System.out.println(n*2);}}\n",
}


@pytest.fixture(scope="module")
def sandbox() -> DockerSandbox:
    return DockerSandbox()


@pytest.mark.parametrize("language", ["python", "cpp", "java"])
def test_languages_pass_and_fail(sandbox: DockerSandbox, language: str) -> None:
    r = sandbox.run_sync(language, DOUBLE[language],
                         [TestCase(input="3\n", output="6\n"), TestCase(input="5\n", output="11\n")])
    assert r.compiled
    assert r.tests_passed == 1 and r.tests_failed == 1 and not r.passed


@pytest.mark.parametrize("language,code", [("python", "def f(:\n"), ("cpp", "int main( {"),
                                           ("java", "public class Main { oops }")])
def test_compile_errors_reported(sandbox: DockerSandbox, language: str, code: str) -> None:
    r = sandbox.run_sync(language, code, [TestCase(input="", output="")])
    assert not r.compiled and r.compile_error


def test_isolation(sandbox: DockerSandbox) -> None:
    net = sandbox.run_sync("python", "import socket\nsocket.create_connection(('1.1.1.1', 53), timeout=3)",
                           [TestCase()])
    assert net.cases[0].exit_code != 0
    ro = sandbox.run_sync("python", "open('/work/evil', 'w')", [TestCase()])
    assert "Read-only file system" in ro.cases[0].stderr
    who = sandbox.run_sync("python", "import os; print(os.getuid())", [TestCase()])
    assert who.cases[0].stdout.strip() == "65534"
    loop = sandbox.run_sync("python", "while True: pass", [TestCase()])
    assert loop.cases[0].timed_out
    fork = sandbox.run_sync("python", "import os\nfor _ in range(500):\n    os.fork()", [TestCase()])
    assert fork.cases[0].exit_code != 0  # pid limit stops the fork bomb


def test_reference_solutions_pass_hidden_tests(sandbox: DockerSandbox) -> None:
    """Sanity-check that generated coding problems are solvable: run a correct Python solution."""
    import random

    tpl = qb.TEMPLATES["code-brackets"]
    rng = random.Random(5)
    inst = qb.finalize(tpl, tpl.gen(rng), rng, shuffle_options=False)
    solution = (
        "import sys\n"
        "s = sys.stdin.readline().strip()\n"
        "st = []\n"
        "m = {')': '(', ']': '[', '}': '{'}\n"
        "ok = True\n"
        "for ch in s:\n"
        "    if ch in '([{': st.append(ch)\n"
        "    elif not st or st.pop() != m[ch]: ok = False; break\n"
        "print('YES' if ok and not st else 'NO')\n"
    )
    tests = [TestCase(**t) for t in inst["answer_key"]["tests"]]
    r = sandbox.run_sync("python", solution, tests)
    assert r.passed, [c for c in r.cases if not c.passed]
