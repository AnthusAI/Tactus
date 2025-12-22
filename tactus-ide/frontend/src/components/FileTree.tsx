import React, { useEffect, useState } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChevronRight, ChevronDown, Folder, File, Code } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TreeEntry {
  name: string;
  path: string;
  type: 'directory' | 'file';
  extension?: string;
}

interface FileTreeProps {
  workspaceRoot: string | null;
  workspaceName: string | null;
  onFileSelect: (path: string) => void;
  selectedFile: string | null;
}

interface TreeNodeProps {
  entry: TreeEntry;
  level: number;
  onFileSelect: (path: string) => void;
  selectedFile: string | null;
  workspaceRoot: string;
}

const TreeNode: React.FC<TreeNodeProps> = ({ entry, level, onFileSelect, selectedFile, workspaceRoot }) => {
  const API_BASE = import.meta.env.VITE_BACKEND_URL || '';
  const apiUrl = (path: string) => (API_BASE ? `${API_BASE}${path}` : path);

  const [expanded, setExpanded] = useState(false);
  const [children, setChildren] = useState<TreeEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const isDirectory = entry.type === 'directory';
  const isSelected = selectedFile === entry.path;
  const isTactusFile = entry.extension === '.tac';

  const loadChildren = async () => {
    if (!isDirectory || children.length > 0) return;

    setLoading(true);
    try {
      const response = await fetch(apiUrl(`/api/tree?path=${encodeURIComponent(entry.path)}`));
      if (response.ok) {
        const data = await response.json();
        setChildren(data.entries || []);
      }
    } catch (error) {
      console.error('Error loading directory:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleClick = () => {
    if (isDirectory) {
      setExpanded(!expanded);
      if (!expanded && children.length === 0) {
        loadChildren();
      }
    } else {
      onFileSelect(entry.path);
    }
  };

  const getIcon = () => {
    if (isDirectory) {
      return expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />;
    }
    if (isTactusFile) {
      return <Code className="h-4 w-4 text-blue-500" />;
    }
    return <File className="h-4 w-4" />;
  };

  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-1 px-2 py-1 cursor-pointer hover:bg-accent rounded-sm text-sm',
          isSelected && 'bg-accent',
          'transition-colors'
        )}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        onClick={handleClick}
      >
        {getIcon()}
        {isDirectory && <Folder className="h-4 w-4 text-yellow-600" />}
        <span className="truncate">{entry.name}</span>
        {loading && <span className="ml-auto text-xs text-muted-foreground">...</span>}
      </div>
      {isDirectory && expanded && children.length > 0 && (
        <div>
          {children.map((child) => (
            <TreeNode
              key={child.path}
              entry={child}
              level={level + 1}
              onFileSelect={onFileSelect}
              selectedFile={selectedFile}
              workspaceRoot={workspaceRoot}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const FileTree: React.FC<FileTreeProps> = ({ workspaceRoot, workspaceName, onFileSelect, selectedFile }) => {
  const API_BASE = import.meta.env.VITE_BACKEND_URL || '';
  const apiUrl = (path: string) => (API_BASE ? `${API_BASE}${path}` : path);

  const [rootEntries, setRootEntries] = useState<TreeEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!workspaceRoot) {
      setRootEntries([]);
      return;
    }

    const loadRoot = async () => {
      setLoading(true);
      try {
        const response = await fetch(apiUrl('/api/tree'));
        if (response.ok) {
          const data = await response.json();
          setRootEntries(data.entries || []);
        }
      } catch (error) {
        console.error('Error loading workspace root:', error);
      } finally {
        setLoading(false);
      }
    };

    loadRoot();
  }, [workspaceRoot]);

  if (!workspaceRoot) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground p-4">
        No folder opened
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
        Loading...
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="py-2">
        {/* Workspace folder root */}
        <div className="flex items-center gap-1 px-2 py-1 text-sm font-medium">
          <ChevronDown className="h-4 w-4" />
          <Folder className="h-4 w-4 text-yellow-600" />
          <span className="truncate">{workspaceName || 'Workspace'}</span>
        </div>
        {/* Root entries at level 1 */}
        {rootEntries.map((entry) => (
          <TreeNode
            key={entry.path}
            entry={entry}
            level={1}
            onFileSelect={onFileSelect}
            selectedFile={selectedFile}
            workspaceRoot={workspaceRoot}
          />
        ))}
      </div>
    </ScrollArea>
  );
};








