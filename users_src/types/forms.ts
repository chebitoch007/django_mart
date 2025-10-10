// Form validation types
interface FormConfig {
    formId: string;
    validationRules: ValidationRule[];
    submitHandler?: (formData: FormData) => boolean;
}

interface ValidationRule {
    field: string;
    validator: (value: string) => boolean;
    message: string;
}

interface FormData {
    [key: string]: string | boolean;
}

export type { FormConfig, ValidationRule, FormData };