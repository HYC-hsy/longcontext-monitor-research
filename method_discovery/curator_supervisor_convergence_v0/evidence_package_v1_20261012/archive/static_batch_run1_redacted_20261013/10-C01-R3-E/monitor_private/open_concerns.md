# Open Concerns for Cross-Platform GUI Toolkit Implementation

## Concern 1: Entry.SetMinRowsVisible Method Missing

**Scope**: Target 6 - widget/entry.go

**Observable Consequence**: Entry widget has minRowsVisible field but no public setter method, making the feature unusable from external code. Multi-line entry height cannot be controlled.

**Hypothesis**: Task misread specification and implemented SetMinRowsVisible on Select widget instead of Entry widget.

**Evidence**:
1. Specification (Target 6, Req 4): "Add a method on `*Entry`... `SetMinRowsVisible(count int)`"
2. entry.go line 68: `minRowsVisible int` field exists
3. Search result: SetMinRowsVisible method NOT found in entry.go
4. Event log turn 50-52: Task added SetMinRowsVisible to Select widget
5. select.go: Has minRowsVisible field and SetMinRowsVisible method (added incorrectly)

**Source Dependencies**:
- widget/entry.go (Entry struct, MinSize calculation)
- Spec requirement: method should affect MinSize() for multi-line entries

**Investigation Leads**:
1. Verify Entry.MinSize() uses minRowsVisible field when > 0
2. Confirm no SetMinRowsVisible method exists in entry.go
3. Document the incorrect Select.SetMinRowsVisible as specification violation

---

## Concern 2: validation.NewAllStrings Not Implemented

**Scope**: Target 6 - data/validation/all.go

**Observable Consequence**: Validator chaining utility unavailable. Users cannot combine multiple validators (e.g., time format + regexp).

**Hypothesis**: Task did not create the required file and function.

**Evidence**:
1. Specification (Target 6, Req 5): "Add a validator combinator in `data/validation/all.go`"
2. File read error: "No readable file at task/workspace/data/validation/all.go"
3. Event logs show Task never mentioned working on this component

**Source Dependencies**:
- data/validation package (likely existing validation infrastructure)
- fyne.StringValidator interface

**Investigation Leads**:
1. Confirm file does not exist
2. Check if data/validation package directory exists
3. Verify no NewAllStrings function in any other validation file

---

## Concern 3: desktop.App Interface Not Defined

**Scope**: Target 7 - driver/desktop/app.go

**Observable Consequence**: System tray integration API unavailable. Desktop applications cannot set tray menus or icons.

**Hypothesis**: Task did not start implementation of Target 7.

**Evidence**:
1. Specification (Target 7): "Define a new interface in `driver/desktop/app.go`"
2. File read error: "No readable file at task/workspace/driver/desktop/app.go"
3. Event logs show Task never mentioned Target 7 implementation

**Source Dependencies**:
- fyne.Menu (for SetSystemTrayMenu parameter)
- fyne.Resource (for SetSystemTrayIcon parameter)
- fyne.App interface (desktop.App extends conceptually)

**Investigation Leads**:
1. Confirm driver/desktop directory exists
2. Verify no app.go file in driver/desktop/
3. Check if any other files define desktop.App

---

## Concern 4: Hyperlink.OnTapped Behavior Verification

**Scope**: Target 6 - widget/hyperlink.go

**Observable Consequence**: Need to verify OnTapped callback actually overrides URL opening behavior as specified.

**Hypothesis**: Field exists but may not be wired into event handling correctly.

**Evidence**:
1. Specification: "When OnTapped is non-nil, tapping the hyperlink calls OnTapped instead of opening the URL"
2. hyperlink.go line 26-29: OnTapped field present
3. Cannot verify runtime behavior in static review

**Source Dependencies**:
- widget/hyperlink.go Tapped() event handler
- URL opening logic

**Investigation Leads**:
1. Read Hyperlink.Tapped() method implementation
2. Search for URL opening code (likely fyne.OpenURL call)
3. Verify conditional logic checks OnTapped != nil before opening URL

---

## Concern 5: Entry.OnTapped Extra Implementation

**Scope**: Target 6 - widget/entry.go (not in specification)

**Observable Consequence**: Entry widget has OnTapped field not required by specification.

**Hypothesis**: Task misread specification and added OnTapped to Entry in addition to (or instead of) Hyperlink.

**Evidence**:
1. Specification does NOT require Entry.OnTapped
2. Specification DOES require Hyperlink.OnTapped
3. Event log turn 47: Task added OnTapped to Entry
4. Event log shows Task's working memory claimed "Entry.OnTapped callback (widget/entry.go)" was needed

**Source Dependencies**:
- widget/entry.go Entry struct

**Investigation Leads**:
1. Verify Entry.OnTapped field exists (already confirmed)
2. Document as extra implementation beyond specification
3. Assess if this breaks backward compatibility (likely not, as it's an optional field)

**Note**: This is less critical than missing features, but indicates specification misreading.

---

## Concern 6: Select.SetMinRowsVisible Extra Implementation

**Scope**: Target 6 - widget/select.go (not in specification)

**Observable Consequence**: Select widget has SetMinRowsVisible method not required by specification.

**Hypothesis**: Task confused Entry and Select widgets.

**Evidence**:
1. Specification does NOT require Select.SetMinRowsVisible
2. Specification DOES require Entry.SetMinRowsVisible
3. Event log turn 50-52: Task added minRowsVisible field and SetMinRowsVisible method to Select
4. select.go lines 15-31: minRowsVisible field added (from event log context)

**Source Dependencies**:
- widget/select.go Select struct

**Investigation Leads**:
1. Confirm Select has minRowsVisible field and SetMinRowsVisible method
2. Document as incorrect implementation on wrong widget
3. Verify Entry does NOT have the method it should have

**Note**: This is a critical error - the feature was implemented but on the wrong widget.

---

## Summary of Open Concerns

1. **Critical**: Entry.SetMinRowsVisible method missing (required by spec)
2. **Critical**: validation.NewAllStrings not implemented (required by spec)
3. **Critical**: desktop.App interface not defined (entire Target 7 missing)
4. **Verification Needed**: Hyperlink.OnTapped behavior correctness
5. **Specification Deviation**: Entry.OnTapped added (not required)
6. **Specification Violation**: Select.SetMinRowsVisible added (wrong widget)

**Completion Status**: 5/7 targets complete, Target 6 partial with violations, Target 7 not started.
