import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ParameterDeclaration } from '@/types/metadata';
import { FileInput, Play, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ProcedureInputsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  parameters: Record<string, ParameterDeclaration>;
  onSubmit: (values: Record<string, any>) => void;
  onCancel: () => void;
}

export const ProcedureInputsModal: React.FC<ProcedureInputsModalProps> = ({
  open,
  onOpenChange,
  parameters,
  onSubmit,
  onCancel,
}) => {
  const [values, setValues] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Initialize values with defaults when parameters change
  useEffect(() => {
    const initialValues: Record<string, any> = {};
    Object.entries(parameters ?? {}).forEach(([name, param]) => {
      if (!param || typeof param !== 'object') {
        return;
      }
      const paramType = param.type ?? 'string';
      if (param.default !== undefined) {
        initialValues[name] = param.default;
      } else if (paramType === 'boolean') {
        initialValues[name] = false;
      } else if (paramType === 'array') {
        initialValues[name] = [];
      } else if (paramType === 'object') {
        initialValues[name] = {};
      } else if (paramType === 'number') {
        initialValues[name] = 0;
      } else {
        initialValues[name] = '';
      }
    });
    setValues(initialValues);
    setErrors({});
  }, [parameters]);

  const handleChange = (name: string, value: any) => {
    setValues(prev => ({ ...prev, [name]: value }));
    setErrors(prev => ({ ...prev, [name]: '' }));
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    Object.entries(parameters ?? {}).forEach(([name, param]) => {
      if (!param || typeof param !== 'object') {
        return;
      }
      if (param.required) {
        const value = values[name];
        if (value === undefined || value === '' || value === null) {
          newErrors[name] = 'This field is required';
        }
      }
    });
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (validate()) {
      onSubmit(values);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const renderInput = (name: string, param: ParameterDeclaration) => {
    const value = values[name];
    const hasError = !!errors[name];
    const paramType = param.type ?? 'string';
    const paramEnum = Array.isArray(param.enum) ? param.enum : undefined;

    switch (paramType) {
      case 'boolean':
        return (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handleChange(name, !value)}
              className={cn(
                'relative h-6 w-11 rounded-full transition-colors',
                value ? 'bg-primary' : 'bg-muted'
              )}
            >
              <span
                className={cn(
                  'absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-background transition-transform',
                  value && 'translate-x-5'
                )}
              />
            </button>
            <span className="text-sm text-muted-foreground">
              {value ? 'Yes' : 'No'}
            </span>
          </div>
        );

      case 'number':
        return (
          <Input
            type="number"
            value={value ?? ''}
            onChange={(e) => {
              const num = e.target.value === '' ? 0 : parseFloat(e.target.value);
              handleChange(name, isNaN(num) ? 0 : num);
            }}
            className={cn(hasError && 'border-red-500')}
            onKeyDown={handleKeyDown}
          />
        );

      case 'array':
        return (
          <textarea
            placeholder='["item1", "item2"]'
            value={typeof value === 'object' ? JSON.stringify(value, null, 2) : value ?? '[]'}
            onChange={(e) => {
              try {
                handleChange(name, JSON.parse(e.target.value));
              } catch {
                // Keep as string while editing - will validate on submit
                handleChange(name, e.target.value);
              }
            }}
            className={cn(
              'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 font-mono',
              hasError && 'border-red-500'
            )}
          />
        );

      case 'object':
        return (
          <textarea
            placeholder='{"key": "value"}'
            value={typeof value === 'object' ? JSON.stringify(value, null, 2) : value ?? '{}'}
            onChange={(e) => {
              try {
                handleChange(name, JSON.parse(e.target.value));
              } catch {
                handleChange(name, e.target.value);
              }
            }}
            className={cn(
              'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 font-mono',
              hasError && 'border-red-500'
            )}
          />
        );

      case 'string':
      default:
        // Check for enum
        if (paramEnum && paramEnum.length > 0) {
          return (
            <select
              value={value ?? ''}
              onChange={(e) => handleChange(name, e.target.value)}
              className={cn(
                'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
                hasError && 'border-red-500'
              )}
            >
              <option value="">Select...</option>
              {paramEnum.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          );
        }
        return (
          <Input
            type="text"
            value={value ?? ''}
            onChange={(e) => handleChange(name, e.target.value)}
            className={cn(hasError && 'border-red-500')}
            onKeyDown={handleKeyDown}
          />
        );
    }
  };

  const paramList = Object.entries(parameters ?? {}).filter(
    (entry): entry is [string, ParameterDeclaration] => {
      const param = entry[1];
      return !!param && typeof param === 'object';
    }
  );

  if (paramList.length === 0) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileInput className="h-5 w-5" />
            Procedure Inputs
          </DialogTitle>
          <DialogDescription>
            Provide values for the procedure inputs. Required fields are marked with *.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4 max-h-[400px] overflow-y-auto">
          {paramList.map(([name, param]) => {
            const safeParam: ParameterDeclaration = {
              ...param,
              type: param.type ?? 'string',
              required: Boolean(param.required),
              enum: Array.isArray(param.enum) ? param.enum : undefined,
            };

            return (
              <div key={name} className="space-y-2">
                <label htmlFor={name} className="text-sm font-medium">
                  {name}
                  {safeParam.required && <span className="text-red-500 ml-1">*</span>}
                  <span className="text-xs text-muted-foreground ml-2">({safeParam.type})</span>
                </label>
                {safeParam.description && (
                  <p className="text-xs text-muted-foreground">{safeParam.description}</p>
                )}
                {renderInput(name, safeParam)}
                {errors[name] && (
                  <p className="text-xs text-red-500">{errors[name]}</p>
                )}
              </div>
            );
          })}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            <X className="h-4 w-4 mr-2" />
            Cancel
          </Button>
          <Button onClick={handleSubmit}>
            <Play className="h-4 w-4 mr-2" />
            Run Procedure
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
