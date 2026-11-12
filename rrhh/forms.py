from django import forms
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

from .models import Empleado, Departamento, Cargo, Empresa, Sede, Perfil, Banco


# ═══════════════════════════════════════════════════════════
#  VALIDADORES COMUNES
# ═══════════════════════════════════════════════════════════

validate_rif = RegexValidator(
    regex=r"^[JVEGP]-\d{8}-\d$",
    message="Formato inválido. Usa: J-12345678-9 (letra, guion, 8 dígitos, guion, dígito).",
)

validate_cedula = RegexValidator(
    regex=r"^\d{6,9}$",
    message="La cédula debe tener entre 6 y 9 dígitos numéricos.",
)


# ═══════════════════════════════════════════════════════════
#  EMPRESA
# ═══════════════════════════════════════════════════════════

class EmpresaForm(forms.ModelForm):
    """Formulario para crear y editar empresas."""

    rif = forms.CharField(
        max_length=20,
        validators=[validate_rif],
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "J-12345678-9",
                "autocomplete": "off",
            }
        ),
        help_text="Formato: J-12345678-9",
    )

    class Meta:
        model = Empresa
        fields = [
            "tipo",
            "padre",
            "rif",
            "razon_social",
            "nombre_comercial",
            "telefono",
            "email",
            "sitio_web",
            "direccion",
            "ciudad",
            "estado",
            "pais",
            "moneda",
            "zona_horaria",
            "logo",
            "activa",
        ]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "padre": forms.Select(attrs={"class": "form-select"}),
            "razon_social": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "ACME Tecnología, C.A."}
            ),
            "nombre_comercial": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "ACME Tech"}
            ),
            "telefono": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+58 212 1234567"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "contacto@acme.com"}
            ),
            "sitio_web": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://acme.com"}
            ),
            "direccion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "ciudad": forms.TextInput(attrs={"class": "form-control"}),
            "estado": forms.TextInput(attrs={"class": "form-control"}),
            "pais": forms.TextInput(
                attrs={"class": "form-control", "maxlength": 2}
            ),
            "moneda": forms.TextInput(
                attrs={"class": "form-control", "maxlength": 3}
            ),
            "zona_horaria": forms.TextInput(attrs={"class": "form-control"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "tipo": "Tipo de empresa",
            "padre": "Empresa matriz",
            "rif": "RIF",
            "razon_social": "Razón social",
            "nombre_comercial": "Nombre comercial",
            "telefono": "Teléfono",
            "email": "Correo electrónico",
            "sitio_web": "Sitio web",
            "direccion": "Dirección fiscal",
            "ciudad": "Ciudad",
            "estado": "Estado",
            "pais": "País",
            "moneda": "Moneda",
            "zona_horaria": "Zona horaria",
            "logo": "Logo",
            "activa": "¿Activa?",
        }
        help_texts = {
            "pais": "Código ISO de 2 letras (ej: VE, US)",
            "moneda": "Código ISO de 3 letras (ej: VES, USD)",
            "zona_horaria": "Ej: America/Caracas",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Evitar que una empresa sea su propia matriz
        if self.instance.pk:
            self.fields["padre"].queryset = Empresa.objects.exclude(pk=self.instance.pk)

    def clean_rif(self):
        """Normaliza y valida unicidad del RIF."""
        rif = self.cleaned_data.get("rif", "").upper().strip()
        qs = Empresa.objects.filter(rif=rif)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe una empresa con este RIF.")
        return rif

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        return email.lower() if email else email

    def clean_pais(self):
        pais = self.cleaned_data.get("pais", "").upper().strip()
        if pais and len(pais) != 2:
            raise forms.ValidationError("El país debe ser un código de 2 letras (ISO).")
        return pais or "VE"

    def clean_moneda(self):
        moneda = self.cleaned_data.get("moneda", "").upper().strip()
        if moneda and len(moneda) != 3:
            raise forms.ValidationError("La moneda debe ser un código de 3 letras (ISO).")
        return moneda or "VES"

    def clean(self):
        cleaned = super().clean()
        padre = cleaned.get("padre")
        tipo = cleaned.get("tipo")

        # Una empresa no puede ser su propia matriz
        if padre and self.instance.pk and padre.pk == self.instance.pk:
            self.add_error("padre", "Una empresa no puede ser su propia matriz.")

        # Solo las filiales pueden tener matriz
        if padre and tipo == "matriz":
            self.add_error(
                "tipo",
                "Una empresa matriz no puede tener otra empresa matriz como padre.",
            )

        return cleaned


# ═══════════════════════════════════════════════════════════
#  SEDE
# ═══════════════════════════════════════════════════════════

class SedeForm(forms.ModelForm):
    """Formulario para crear y editar sedes."""

    class Meta:
        model = Sede
        fields = [
            "empresa",
            "tipo",
            "es_principal",
            "codigo",
            "nombre",
            "direccion",
            "ciudad",
            "estado",
            "pais",
            "codigo_postal",
            "telefono",
            "email",
            "activa",
        ]
        widgets = {
            "empresa": forms.Select(attrs={"class": "form-select"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "es_principal": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "codigo": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "SUC-01",
                    "autocomplete": "off",
                }
            ),
            "nombre": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Sede Principal Caracas"}
            ),
            "direccion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "ciudad": forms.TextInput(attrs={"class": "form-control"}),
            "estado": forms.TextInput(attrs={"class": "form-control"}),
            "pais": forms.TextInput(
                attrs={"class": "form-control", "maxlength": 2}
            ),
            "codigo_postal": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "1010"}
            ),
            "telefono": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+58 212 1234567"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "sede@acme.com"}
            ),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "empresa": "Empresa",
            "tipo": "Tipo de sede",
            "es_principal": "¿Es la sede principal?",
            "codigo": "Código",
            "nombre": "Nombre de la sede",
            "direccion": "Dirección",
            "ciudad": "Ciudad",
            "estado": "Estado",
            "pais": "País",
            "codigo_postal": "Código postal",
            "telefono": "Teléfono",
            "email": "Correo electrónico",
            "activa": "¿Activa?",
        }
        help_texts = {
            "codigo": "Código único dentro de la empresa. Ej: PRINCIPAL, SUC-01",
            "es_principal": "Marca esta sede como la principal de la empresa.",
        }

    def clean_codigo(self):
        """Normaliza y valida unicidad por empresa."""
        codigo = self.cleaned_data.get("codigo", "").upper().strip()
        empresa = self.cleaned_data.get("empresa")

        if empresa and codigo:
            qs = Sede.objects.filter(empresa=empresa, codigo=codigo)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "Ya existe una sede con este código en la empresa."
                )
        return codigo

    def clean_pais(self):
        pais = self.cleaned_data.get("pais", "").upper().strip()
        if pais and len(pais) != 2:
            raise forms.ValidationError("El país debe ser un código de 2 letras (ISO).")
        return pais or "VE"

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        return email.lower() if email else email


# ═══════════════════════════════════════════════════════════
#  CARGO
# ═══════════════════════════════════════════════════════════

class CargoForm(forms.ModelForm):
    """Formulario para crear y editar cargos."""

    class Meta:
        model = Cargo
        fields = [
            "codigo",
            "nombre",
            "descripcion",
            "salario_min",
            "salario_max",
            "activo",
        ]
        widgets = {
            "codigo": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "DEV-SR",
                    "autocomplete": "off",
                }
            ),
            "nombre": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Desarrollador Senior"}
            ),
            "descripcion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "salario_min": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "salario_max": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "codigo": "Código",
            "nombre": "Nombre del cargo",
            "descripcion": "Descripción",
            "salario_min": "Salario mínimo (Bs.)",
            "salario_max": "Salario máximo (Bs.)",
            "activo": "¿Activo?",
        }

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo", "").upper().strip()
        qs = Cargo.objects.filter(codigo=codigo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un cargo con este código.")
        return codigo

    def clean_nombre(self):
        nombre = self.cleaned_data.get("nombre", "").strip()
        qs = Cargo.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un cargo con este nombre.")
        return nombre

    def clean(self):
        cleaned = super().clean()
        sal_min = cleaned.get("salario_min")
        sal_max = cleaned.get("salario_max")

        if sal_min is not None and sal_max is not None and sal_max < sal_min:
            self.add_error(
                "salario_max",
                "El salario máximo no puede ser menor que el mínimo.",
            )

        return cleaned


# ═══════════════════════════════════════════════════════════
#  DEPARTAMENTO
# ═══════════════════════════════════════════════════════════

class DepartamentoForm(forms.ModelForm):
    """Formulario para crear y editar departamentos."""

    class Meta:
        model = Departamento
        fields = [
            "empresa",
            "padre",
            "codigo",
            "nombre",
            "descripcion",
            "presupuesto_anual",
            "responsable",
            "activo",
        ]
        widgets = {
            "empresa": forms.Select(attrs={"class": "form-select"}),
            "padre": forms.Select(attrs={"class": "form-select"}),
            "codigo": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "TI",
                    "autocomplete": "off",
                }
            ),
            "nombre": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Tecnología"}
            ),
            "descripcion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "presupuesto_anual": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "responsable": forms.Select(attrs={"class": "form-select"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "empresa": "Empresa",
            "padre": "Departamento padre",
            "codigo": "Código",
            "nombre": "Nombre del departamento",
            "descripcion": "Descripción",
            "presupuesto_anual": "Presupuesto anual (Bs.)",
            "responsable": "Responsable",
            "activo": "¿Activo?",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Evitar que un departamento sea su propio padre
        if self.instance.pk:
            self.fields["padre"].queryset = Departamento.objects.exclude(
                pk=self.instance.pk
            )

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo", "").upper().strip()
        empresa = self.cleaned_data.get("empresa")

        if empresa and codigo:
            qs = Departamento.objects.filter(empresa=empresa, codigo=codigo)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "Ya existe un departamento con este código en la empresa."
                )
        return codigo

    def clean(self):
        cleaned = super().clean()
        padre = cleaned.get("padre")
        empresa = cleaned.get("empresa")

        # Validar que el padre sea de la misma empresa
        if padre and empresa and padre.empresa_id != empresa.id:
            self.add_error(
                "padre",
                "El departamento padre debe pertenecer a la misma empresa.",
            )

        # Evitar ciclos
        if padre and self.instance.pk and padre.pk == self.instance.pk:
            self.add_error("padre", "Un departamento no puede ser su propio padre.")

        return cleaned


# ═══════════════════════════════════════════════════════════
#  EMPLEADO
# ═══════════════════════════════════════════════════════════

class EmpleadoForm(forms.ModelForm):
    """Formulario para crear y editar empleados."""

    numero_empleado = forms.CharField(
        max_length=30,
        validators=[
            RegexValidator(
                regex=r"^EMP-\d{4}$",
                message="El número debe tener el formato EMP-0001.",
            )
        ],
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "EMP-0001",
                "autocomplete": "off",
            }
        ),
    )

    cedula = forms.CharField(
        max_length=20,
        validators=[validate_cedula],
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "12345678",
                "autocomplete": "off",
            }
        ),
        help_text="Solo el número, sin la letra (V, E o P).",
    )

    class Meta:
        model = Empleado
        fields = [
            "empresa",
            "sede",
            "numero_empleado",
            "nacionalidad",
            "cedula",
            "nombre",
            "apellido_paterno",
            "apellido_materno",
            "fecha_nacimiento",
            "genero",
            "estado_civil",
            "email",
            "telefono",
            "telefono_habitacion",
            "direccion",
            "ciudad",
            "estado",
            "pais",
            "cargo",
            "departamento",
            "jefe",
            "fecha_ingreso",
            "fecha_egreso",
            "tipo_contrato",
            "tipo_jornada",
            "estatus",
            "salario_base",
            "periodicidad_pago",
            "banco",
            "cuenta_bancaria",
            "clabe",
        ]
        widgets = {
            "empresa": forms.Select(attrs={"class": "form-select"}),
            "sede": forms.Select(attrs={"class": "form-select"}),
            "nacionalidad": forms.Select(attrs={"class": "form-select"}),
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "apellido_paterno": forms.TextInput(attrs={"class": "form-control"}),
            "apellido_materno": forms.TextInput(attrs={"class": "form-control"}),
            "fecha_nacimiento": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "genero": forms.Select(attrs={"class": "form-select"}),
            "estado_civil": forms.Select(attrs={"class": "form-select"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+58 412 1234567"}
            ),
            "telefono_habitacion": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+58 212 1234567"}
            ),
            "direccion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "ciudad": forms.TextInput(attrs={"class": "form-control"}),
            "estado": forms.TextInput(attrs={"class": "form-control"}),
            "pais": forms.TextInput(
                attrs={"class": "form-control", "maxlength": 2}
            ),
            "cargo": forms.Select(attrs={"class": "form-select"}),
            "departamento": forms.Select(attrs={"class": "form-select"}),
            "jefe": forms.Select(attrs={"class": "form-select"}),
            "fecha_ingreso": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "fecha_egreso": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "tipo_contrato": forms.Select(attrs={"class": "form-select"}),
            "tipo_jornada": forms.Select(attrs={"class": "form-select"}),
            "estatus": forms.Select(attrs={"class": "form-select"}),
            "salario_base": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "periodicidad_pago": forms.Select(attrs={"class": "form-select"}),
            "banco": forms.Select(attrs={"class": "form-select"}),
            "cuenta_bancaria": forms.TextInput(attrs={"class": "form-control"}),
            "clabe": forms.TextInput(
                attrs={"class": "form-control", "maxlength": 18}
            ),
        }
        labels = {
            "empresa": "Empresa",
            "sede": "Sede",
            "numero_empleado": "Número de empleado",
            "nacionalidad": "Nacionalidad",
            "cedula": "Cédula / Pasaporte",
            "nombre": "Nombre",
            "apellido_paterno": "Apellido paterno",
            "apellido_materno": "Apellido materno",
            "fecha_nacimiento": "Fecha de nacimiento",
            "genero": "Género",
            "estado_civil": "Estado civil",
            "email": "Correo electrónico",
            "telefono": "Teléfono móvil",
            "telefono_habitacion": "Teléfono de habitación",
            "direccion": "Dirección",
            "ciudad": "Ciudad",
            "estado": "Estado",
            "pais": "País",
            "cargo": "Cargo",
            "departamento": "Departamento",
            "jefe": "Jefe directo",
            "fecha_ingreso": "Fecha de ingreso",
            "fecha_egreso": "Fecha de egreso",
            "tipo_contrato": "Tipo de contrato",
            "tipo_jornada": "Tipo de jornada",
            "estatus": "Estatus",
            "salario_base": "Salario base mensual (Bs.)",
            "periodicidad_pago": "Periodicidad de pago",
            "banco": "Banco",
            "cuenta_bancaria": "Número de cuenta",
            "clabe": "CLABE interbancaria",
        }
        help_texts = {
            "pais": "Código ISO de 2 letras (ej: VE)",
            "fecha_egreso": "Déjalo vacío si el empleado sigue activo.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrar sedes según la empresa seleccionada (si viene en el POST)
        empresa_id = None
        if self.data.get("empresa"):
            empresa_id = self.data.get("empresa")
        elif self.instance.pk and self.instance.empresa_id:
            empresa_id = self.instance.empresa_id

        if empresa_id:
            self.fields["sede"].queryset = Sede.objects.filter(
                empresa_id=empresa_id, activa=True
            )
            self.fields["departamento"].queryset = Departamento.objects.filter(
                empresa_id=empresa_id, activo=True
            )
        else:
            self.fields["sede"].queryset = Sede.objects.none()
            self.fields["departamento"].queryset = Departamento.objects.filter(
                activo=True
            )

        # Jefes: excluir al propio empleado
        if self.instance.pk:
            self.fields["jefe"].queryset = Empleado.objects.exclude(
                pk=self.instance.pk
            )

        # Filtrar cargos activos
        self.fields["cargo"].queryset = Cargo.objects.filter(activo=True)
        
        # Filtrar bancos activos y ordenar por código Sudeban
        self.fields["banco"].queryset = Banco.objects.filter(activo=True).order_by("codigo")
        self.fields["banco"].empty_label = "— Seleccionar banco —"

    def clean_numero_empleado(self):
        numero = self.cleaned_data.get("numero_empleado", "").upper().strip()
        empresa = self.cleaned_data.get("empresa")

        if empresa and numero:
            qs = Empleado.objects.filter(empresa=empresa, numero_empleado=numero)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "Ya existe un empleado con este número en la empresa."
                )
        return numero

    def clean_cedula(self):
        cedula = self.cleaned_data.get("cedula", "").replace(".", "").replace(" ", "").strip()
        return cedula

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise forms.ValidationError("El correo electrónico es obligatorio.")

        qs = Empleado.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un empleado con este correo.")
        return email

    def clean_salario_base(self):
        salario = self.cleaned_data.get("salario_base")
        if salario is not None and salario <= 0:
            raise forms.ValidationError("El salario debe ser mayor a cero.")
        return salario

    def clean(self):
        cleaned = super().clean()

        empresa = cleaned.get("empresa")
        sede = cleaned.get("sede")
        departamento = cleaned.get("departamento")
        nacionalidad = cleaned.get("nacionalidad")
        cedula = cleaned.get("cedula")
        fecha_ingreso = cleaned.get("fecha_ingreso")
        fecha_egreso = cleaned.get("fecha_egreso")
        estatus = cleaned.get("estatus")

        # Validar que la sede pertenece a la empresa
        if sede and empresa and sede.empresa_id != empresa.id:
            self.add_error(
                "sede",
                "La sede seleccionada no pertenece a la empresa elegida.",
            )

        # Validar que el departamento pertenece a la empresa
        if departamento and empresa and departamento.empresa_id != empresa.id:
            self.add_error(
                "departamento",
                "El departamento seleccionado no pertenece a la empresa elegida.",
            )

        # Validar unicidad de cédula por empresa
        if empresa and nacionalidad and cedula:
            qs = Empleado.objects.filter(
                empresa=empresa,
                nacionalidad=nacionalidad,
                cedula=cedula,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "cedula",
                    "Ya existe un empleado con esta cédula en la empresa.",
                )

        # Validar fechas
        if fecha_ingreso and fecha_egreso and fecha_egreso < fecha_ingreso:
            self.add_error(
                "fecha_egreso",
                "La fecha de egreso no puede ser anterior a la fecha de ingreso.",
            )

        # Si el estatus es baja, debe tener fecha de egreso
        if estatus == "baja" and not fecha_egreso:
            self.add_error(
                "fecha_egreso",
                "Si el empleado está dado de baja, debes indicar la fecha de egreso.",
            )

        return cleaned


# ═══════════════════════════════════════════════════════════
#  PERFIL
# ═══════════════════════════════════════════════════════════

class PerfilForm(forms.ModelForm):
    """Formulario para editar el perfil de un usuario."""

    class Meta:
        model = Perfil
        fields = [
            "rol",
            "empresa",
            "empleado",
            "cargo",
            "telefono",
        ]
        widgets = {
            "rol": forms.Select(attrs={"class": "form-select"}),
            "empresa": forms.Select(attrs={"class": "form-select"}),
            "empleado": forms.Select(attrs={"class": "form-select"}),
            "cargo": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+58 412 1234567"}
            ),
        }
        labels = {
            "rol": "Rol",
            "empresa": "Empresa",
            "empleado": "Empleado vinculado",
            "cargo": "Cargo",
            "telefono": "Teléfono",
        }
        help_texts = {
            "empresa": "Deja vacío para acceso global (solo superadmins).",
            "empleado": "Vincula este usuario con un empleado existente.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si el usuario no es superadmin, solo puede elegir su propia empresa
        request = kwargs.get("request") or self.request if hasattr(self, "request") else None
        if request and not request.user.is_superuser:
            if hasattr(request.user, "perfil") and request.user.perfil.empresa:
                self.fields["empresa"].queryset = Empresa.objects.filter(
                    pk=request.user.perfil.empresa_id
                )
                self.fields["empresa"].disabled = True

        # Solo cargos y empleados activos
        self.fields["empleado"].queryset = Empleado.objects.filter(estatus="activo")

    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get("rol")
        empresa = cleaned.get("empresa")

        # Solo superadmin puede tener empresa vacía
        if rol == "superadmin" and empresa:
            self.add_error(
                "empresa",
                "Un superadministrador no debe tener empresa asignada (acceso global).",
            )

        if rol != "superadmin" and not empresa:
            self.add_error(
                "empresa",
                "Debes asignar una empresa al usuario (excepto superadmins).",
            )

        return cleaned