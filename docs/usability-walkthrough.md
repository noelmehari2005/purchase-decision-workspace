# Local accessibility and usability walkthrough

Use fictional data and the account-free example at `http://127.0.0.1:5173`. Do not save, delete an account/workspace, enter a real budget, or create credentials for this exercise. The observer should record what actually happens, including confusing wording and lost focus. A guided session with the developer/user is useful feedback but is not an independent usability study or accessibility certification.

## Guided keyboard pass

1. Use Tab and Shift-Tab to find the navigation controls. Activate a step with Enter. Check that its heading receives visible focus.
2. Open Candidates and activate Add another laptop. Focus should enter the new product-name field.
3. Leave that new draft blank and activate Confirm reviewed laptop. Note whether the error is visible/announced and identifies the missing information.
4. Remove only the newly created unsaved draft. Focus should return to Add another laptop. Do not remove an existing saved candidate.
5. Use Skip to workspace. Check that it reaches the main content without stepping through the header again.

On some Mac configurations, Tab does not visit every control until keyboard navigation is enabled. Record that environment condition rather than silently changing system settings. VoiceOver navigation can be used for the reading pass below.

## Screen-reader reading pass

Turn VoiceOver on yourself if you want to use it. Apple documents Command-F5; depending on keyboard function-key settings, Fn may also be needed. The same shortcut turns it off. See [Apple's VoiceOver introduction](https://support.apple.com/en-lb/guide/voiceover/vo4be8816d70/mac). Use Control-Option plus the arrow keys to explore; Control-Option is the usual VoiceOver modifier. If this is your first screen-reader session, take it slowly and report navigation trouble separately from app-label trouble.

Listen for the following, and report the wording you hear:

- Product name and Exact configuration as distinct fields; the configuration explanation as help rather than part of the field name.
- Required-tool compatibility as the field name, with its evidence explanation available separately.
- Confirmation status when a fictional laptop is reviewed.
- For a later signed-in import review: each Keep my entry checkbox identifies the particular field. Source tables have labeled scroll regions.

The coding session checks accessible names/roles and focus. The account holder's actual spoken-output feedback is recorded separately; the agent does not infer a screen-reader pass from a DOM tree.

## Magnification pass

In Chrome, set page zoom to 200% yourself using its menu or Command-plus. Check Needs, Candidates and Compare & plan for clipped text, unreachable actions, overlapping fields and page-wide horizontal scrolling. Source tables may scroll within their labeled regions. Reset with Command-0 after the check. [Chrome zoom help](https://support.google.com/chrome/answer/96810).

Do not confuse a narrow viewport test with actual browser zoom. Milestone 7 tested narrow viewports; this pass records browser magnification separately.

## Short comprehension tasks

For a participant who has not designed the app, give the task without explaining the expected answer:

1. Describe what Alex needs and whether you would investigate the existing laptop before replacing it.
2. Review a fictional candidate. Explain what Needs verification means and which evidence you would look for.
3. Find the monthly contribution and explain whether the app chose it or you did.
4. Explain what will be retained if you close the tab without saving, and what a saved historical review preserves.

Ask the participant to say what they expect before activating an action. Record the path taken, any assistance, and the participant's explanation. Keep the expected distinction (draft/confirmed, unknown/zero, contribution/suggestion, explicit save/history) in the observer's notes rather than coaching the participant.

## Result template

- Date and tester role (guided developer/user or independent participant):
- Browser, screen reader/version and zoom used:
- Task completed without assistance / with assistance / not completed:
- Exact unclear label or behavior:
- Expected behavior:
- Observed behavior:
- Fix and recheck result:

Do not record passwords, real financial inputs, private account screenshots or reset links. A brief description of the issue is enough.
