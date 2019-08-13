import types


class DecoratedMethodsMetaClass(type):
    """ A Meta class that looks for a "decorators" list attribute on the
        class and applies all functions (decorators) in that list to all
        methods in the class
    """
    def __new__(cls, class_name, parents, attrs):
        if "decorators" in attrs:
            decorators = attrs["decorators"]

            # Iterating over all attrs of the class and applying all of the
            # decorators to all attributes that are methods
            for attr_name, attr_value in attrs.items():
                if isinstance(attr_value, types.FunctionType):
                    method = attr_value
                    for decorator in decorators:
                        method = decorator(method)
                    attrs[attr_name] = method

        return type.__new__(cls, class_name, parents, attrs)
