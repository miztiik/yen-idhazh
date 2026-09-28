"""What happens when a task module cannot even be imported? Discovery must stop the shard."""

raise ImportError("a dependency this task needs at module scope is not installed")
