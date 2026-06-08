/*
 * SPDX-License-Identifier: MIT
 */

#define DT_DRV_COMPAT zmk_behavior_logos_kana

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

#include <drivers/behavior.h>
#include <dt-bindings/logos_kana/keys.h>
#include <dt-bindings/zmk/keys.h>
#include <dt-bindings/zmk/modifiers.h>
#include <zmk/behavior.h>
#include <zmk/events/keycode_state_changed.h>
#include <zmk/hid.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#define LOGOS_KANA_OUTPUT_END 0
#define LOGOS_KANA_MAX_OUTPUT_LEN 6
#define LOGOS_KANA_MOD_MASK                                                                      \
    (MOD_LCTL | MOD_RCTL | MOD_LSFT | MOD_RSFT | MOD_LALT | MOD_RALT | MOD_LGUI | MOD_RGUI)

struct logos_kana_mapping {
    uint8_t key1;
    uint8_t key2;
    uint32_t output[LOGOS_KANA_MAX_OUTPUT_LEN];
};

#include "../logos_kana_map.inc"

struct logos_kana_pending {
    bool active;
    uint8_t key;
    uint32_t fallback;
};

static struct logos_kana_pending pending;
static struct k_work_delayable pending_work;

static bool is_valid_key(uint32_t key) { return key < LOGOS_KANA_KEY_COUNT; }

static bool mods_are_active(void) { return (zmk_hid_get_explicit_mods() & LOGOS_KANA_MOD_MASK) != 0; }

static void tap_keycode(uint32_t keycode, int64_t timestamp) {
    raise_zmk_keycode_state_changed_from_encoded(keycode, true, timestamp);
    raise_zmk_keycode_state_changed_from_encoded(keycode, false, timestamp);
}

static const struct logos_kana_mapping *find_mapping(uint8_t key1, uint8_t key2) {
    for (int i = 0; i < ARRAY_SIZE(logos_kana_mappings); i++) {
        const struct logos_kana_mapping *mapping = &logos_kana_mappings[i];
        if (mapping->key2 == LOGOS_KANA_KEY_NONE) {
            if (key2 == LOGOS_KANA_KEY_NONE && mapping->key1 == key1) {
                return mapping;
            }
            continue;
        }

        if ((mapping->key1 == key1 && mapping->key2 == key2) ||
            (mapping->key1 == key2 && mapping->key2 == key1)) {
            return mapping;
        }
    }

    return NULL;
}

static void type_mapping(const struct logos_kana_mapping *mapping, int64_t timestamp) {
    if (mapping == NULL) {
        return;
    }

    for (int i = 0; i < LOGOS_KANA_MAX_OUTPUT_LEN; i++) {
        if (mapping->output[i] == LOGOS_KANA_OUTPUT_END) {
            break;
        }
        tap_keycode(mapping->output[i], timestamp);
    }
}

static void flush_pending(int64_t timestamp) {
    if (!pending.active) {
        return;
    }

    uint32_t fallback = pending.fallback;
    const struct logos_kana_mapping *mapping = find_mapping(pending.key, LOGOS_KANA_KEY_NONE);
    pending.active = false;

    if (mods_are_active()) {
        tap_keycode(fallback, timestamp);
    } else {
        type_mapping(mapping, timestamp);
    }
}

static void pending_timeout(struct k_work *work) {
    ARG_UNUSED(work);
    flush_pending(k_uptime_get());
}

static void set_pending(uint8_t key, uint32_t fallback) {
    pending.active = true;
    pending.key = key;
    pending.fallback = fallback;
    k_work_reschedule(&pending_work, K_MSEC(CONFIG_LOGOS_KANA_COMBO_TIMEOUT_MS));
}

static int on_keymap_binding_pressed(struct zmk_behavior_binding *binding,
                                     struct zmk_behavior_binding_event event) {
    uint32_t key = binding->param1;
    uint32_t fallback = binding->param2;

    if (!is_valid_key(key)) {
        return ZMK_BEHAVIOR_OPAQUE;
    }

    if (mods_are_active()) {
        flush_pending(event.timestamp);
        tap_keycode(fallback, event.timestamp);
        return ZMK_BEHAVIOR_OPAQUE;
    }

    if (!pending.active) {
        set_pending(key, fallback);
        return ZMK_BEHAVIOR_OPAQUE;
    }

    if (pending.key == key) {
        return ZMK_BEHAVIOR_OPAQUE;
    }

    const struct logos_kana_mapping *combo = find_mapping(pending.key, key);
    if (combo != NULL) {
        k_work_cancel_delayable(&pending_work);
        pending.active = false;
        type_mapping(combo, event.timestamp);
        return ZMK_BEHAVIOR_OPAQUE;
    }

    flush_pending(event.timestamp);
    set_pending(key, fallback);
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_keymap_binding_released(struct zmk_behavior_binding *binding,
                                      struct zmk_behavior_binding_event event) {
    uint32_t key = binding->param1;

    if (pending.active && pending.key == key) {
        k_work_cancel_delayable(&pending_work);
        flush_pending(event.timestamp);
    }

    return ZMK_BEHAVIOR_OPAQUE;
}

static int behavior_logos_kana_init(const struct device *dev) {
    ARG_UNUSED(dev);

    pending.active = false;
    k_work_init_delayable(&pending_work, pending_timeout);
    return 0;
}

static const struct behavior_driver_api behavior_logos_kana_driver_api = {
    .binding_pressed = on_keymap_binding_pressed,
    .binding_released = on_keymap_binding_released,
};

#define KP_INST(n)                                                                                 \
    BEHAVIOR_DT_INST_DEFINE(n, behavior_logos_kana_init, NULL, NULL, NULL, POST_KERNEL,            \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &behavior_logos_kana_driver_api);

DT_INST_FOREACH_STATUS_OKAY(KP_INST)
