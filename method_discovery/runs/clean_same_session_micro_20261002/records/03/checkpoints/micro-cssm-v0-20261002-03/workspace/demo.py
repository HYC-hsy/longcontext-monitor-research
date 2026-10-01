from view import View
view = View('first')
view.refresh()
print(repr(view.rendered))
view.title = 'second'
view.refresh()
print(repr(view.rendered))
