// Lock the screen without animation when the system is about to suspend.
//
// On "about to suspend", gnome-settings-daemon switches the display off at once,
// while gnome-shell is still animating the lock screen (0.3 s pause + 0.3 s
// fade). With mutter 48 the frame clock does not advance while the display is
// off: a pending frame is only completed when a newer frame supersedes it, and
// a second frame is only dispatched when rendering is slow (triple buffering).
// The lock therefore never completes before the suspend, gnome-shell keeps its
// delay inhibitor until logind's 5 s timeout, and the lock finishes after
// resume and blanks the screen. Locking without animation makes the shield
// active synchronously, before the display goes off.

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as LoginManager from 'resource:///org/gnome/shell/misc/loginManager.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class SleepLockExtension extends Extension {
    enable() {
        const shield = Main.screenShield;
        if (!shield)
            return;

        const origLock = Object.getPrototypeOf(shield).lock;
        this._shield = shield;
        shield.lock = function (animate) {
            if (LoginManager.getLoginManager().preparingForSleep)
                animate = false;
            return origLock.call(this, animate);
        };
    }

    disable() {
        if (this._shield) {
            delete this._shield.lock;   // back to the prototype's method
            this._shield = null;
        }
    }
}
