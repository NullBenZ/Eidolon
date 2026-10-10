def test_unrecognized_bind_is_unknown():
    from eidolon.adapters.hyprland.parser import parse_config
    
    config_text = "bind = Super+T, exec, firefoxx"
    config = parse_config(config_text)
    
    assert len(config.binds) == 0
    assert len(config.unknowns) == 1
    assert config.unknowns[0].content == "bind = Super+T, exec, firefoxx"
    
def test_comparator_unknowns():
    from eidolon.adapters.hyprland.parser import parse_config
    from eidolon.adapters.hyprland.comparator import compare_configs
    
    old_c = parse_config("bind = Super+T, exec, firefoxx")
    new_c = parse_config("bind = Super+T, exec, firefox")
    
    changes = compare_configs(old_c, new_c, [])
    # Should report one removed and one added unknown
    assert len(changes) == 2
    assert changes[0].category == "Unknown"
    assert changes[1].category == "Unknown"
