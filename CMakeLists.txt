if(CONFIG_SHIELD_TORABO_TSUKI_LP_LEFT OR CONFIG_SHIELD_TORABO_TSUKI_LP_RIGHT OR CONFIG_LOGOS_KANA)
  zephyr_library()
  zephyr_include_directories(${APPLICATION_SOURCE_DIR}/include include)
endif()

if(CONFIG_SHIELD_TORABO_TSUKI_LP_LEFT OR CONFIG_SHIELD_TORABO_TSUKI_LP_RIGHT)
  zephyr_library_sources(src/board.c src/mini_trackpad_init_reg.c)
endif()

if(CONFIG_LOGOS_KANA AND ((NOT CONFIG_ZMK_SPLIT) OR CONFIG_ZMK_SPLIT_ROLE_CENTRAL))
  zephyr_library_sources(src/behaviors/behavior_logos_kana.c)
endif()
