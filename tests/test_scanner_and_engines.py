import os
import tempfile
from aedile.core.models import Import, SourceFile, Symbol
from aedile.core.scanner import Scanner
from aedile.infrastructure.cache import ScanCache
from aedile.shared.config import Config


def test_scanner_orchestration() -> None:
    config = Config.default()
    config.src_dirs = ["src"]
    
    # Create temp project structure
    temp_dir = tempfile.mkdtemp()
    src_dir = os.path.join(temp_dir, "src")
    os.makedirs(src_dir)

    code = "import os\nfrom . import child\n"
    file_path = os.path.join(src_dir, "parent.py")
    child_path = os.path.join(src_dir, "child.py")
    
    with open(file_path, "w", encoding="utf-8") as f1, open(child_path, "w", encoding="utf-8") as f2:
        f1.write(code)
        f2.write("# child\n")

    try:
        cache = ScanCache(os.path.join(temp_dir, ".aedile_cache"))
        scanner = Scanner(config, cache)
        
        # Test scan project
        files, graph = scanner.scan_project(temp_dir)
        assert len(files) == 2
        assert "parent" in graph.nodes
        assert "child" in graph.nodes

        # Test running rules (should run cleanly with 0 violations)
        violations = scanner.run_rules(files, graph)
        assert len(violations) == 0
    finally:
        import shutil
        shutil.rmtree(temp_dir)


def test_scan_cache_operations() -> None:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        cache_path = f.name

    try:
        cache = ScanCache(cache_path)
        sf = SourceFile(
            filepath="/proj/src/a.py",
            relative_path="src/a.py",
            file_hash="xyz",
            file_size=100,
            language="python",
            imports=[Import(module="b", names=[], line=1)],
            symbols=[Symbol(name="A", kind="class", line=2, end_line=5)],
        )
        
        # Test set
        cache.set(sf.filepath, sf)
        
        # Test get (hit)
        sf_cached = cache.get(sf.filepath, "xyz")
        assert sf_cached is not None
        assert sf_cached.file_hash == "xyz"
        assert len(sf_cached.imports) == 1
        assert sf_cached.imports[0].module == "b"

        # Test get (miss due to hash)
        assert cache.get(sf.filepath, "abc") is None

        # Test save and reload
        cache.save()
        
        cache_new = ScanCache(cache_path)
        sf_reloaded = cache_new.get(sf.filepath, "xyz")
        assert sf_reloaded is not None
        assert sf_reloaded.file_hash == "xyz"
        assert len(sf_reloaded.symbols) == 1
        assert sf_reloaded.symbols[0].name == "A"

        # Test clear
        cache.clear()
        assert not os.path.exists(cache_path)
    finally:
        if os.path.exists(cache_path):
            os.remove(cache_path)

