from django import forms, template

register = template.Library()


def _widget_class(field):
    widget = field.field.widget
    if isinstance(widget, forms.CheckboxInput):
        return 'lq-check-input'
    if isinstance(widget, forms.Select):
        return 'lq-select'
    if isinstance(widget, forms.FileInput):
        return 'lq-file'
    return 'lq-input'


@register.inclusion_tag('components/form.html')
def lq_form(form):
    """Renderiza um Form Django com os componentes do Lottiq Design System (substitui crispy)."""
    fields = []
    for field in form:
        if field.is_hidden:
            fields.append({'field': field, 'hidden': True})
            continue
        css = _widget_class(field)
        if field.errors and css in ('lq-input', 'lq-select'):
            css += ' is-error'
        described_by = []
        if field.help_text:
            described_by.append(f'{field.auto_id}_help')
        if field.errors:
            described_by.append(f'{field.auto_id}_errors')
        attrs = {'class': css}
        if described_by:
            attrs['aria-describedby'] = ' '.join(described_by)
        if field.errors:
            attrs['aria-invalid'] = 'true'
        field.field.widget.attrs.update(attrs)
        fields.append({
            'field': field,
            'hidden': False,
            'is_checkbox': isinstance(field.field.widget, forms.CheckboxInput),
        })
    return {'form': form, 'fields': fields}
